"""This module provides CRUD operations for Onshape documents."""

import argparse
import asyncio
import io
import json
import logging
import tempfile
from contextlib import contextmanager
from typing import AsyncIterable, Generator, Literal

from kol.onshape.api import OnshapeApi
from kol.onshape.client import OnshapeClient
from kol.onshape.config import ConverterConfig
from kol.onshape.download import download
from kol.onshape.postprocess import postprocess
from PIL import Image

from www.app.crud.base import BaseDbCrud
from www.app.crud.listings import ListingsCrud
from www.app.model import Listing

logger = logging.getLogger(__name__)

MessageLevel = Literal["error", "info", "success", "image", "urdf"]


class QueueHandler(logging.Handler):
    def __init__(self, queue: asyncio.Queue[tuple[str, MessageLevel] | None]) -> None:
        super().__init__()

        self.queue = queue

    def emit(self, record: logging.LogRecord) -> None:
        level = logging.getLevelName(record.levelno).lower()
        queue_level: MessageLevel
        match level:
            case "debug":
                queue_level = "info"
            case "info":
                queue_level = "info"
            case "warning":
                queue_level = "info"
            case "error":
                queue_level = "error"
            case "critical":
                queue_level = "error"
            case _:
                queue_level = "info"
        self.queue.put_nowait((self.format(record), queue_level))


@contextmanager
def capture_logs(
    queue: asyncio.Queue[tuple[str, MessageLevel] | None],
    logger_name: str,
    level: int = logging.INFO,
) -> Generator[None, None, None]:
    logger = logging.getLogger(logger_name)
    original_handlers = logger.handlers[:]
    original_levels = [handler.level for handler in original_handlers]

    handler = QueueHandler(queue)
    handler.setLevel(level)
    logger.addHandler(handler)

    for h in original_handlers:
        h.setLevel(logging.CRITICAL + 1)

    try:
        yield
    finally:
        # Restore original handlers and their levels
        logger.removeHandler(handler)
        for h, lvl in zip(original_handlers, original_levels):
            h.setLevel(lvl)


class OnshapeCrud(ListingsCrud, BaseDbCrud):
    async def onshape_document_exists(self, onshape_url: str) -> bool:
        client = OnshapeClient()
        api = OnshapeApi(client)
        document_info = client.parse_url(onshape_url)
        try:
            await api.get_assembly(document_info)
            return True
        except Exception as e:
            logger.error("Error: %s", e)
            return False

    async def add_onshape_url_to_listing(self, listing_id: str, onshape_url: str | None) -> None:
        if onshape_url is None:
            await self.remove_onshape_url(listing_id)
        else:
            if not await self.onshape_document_exists(onshape_url):
                raise ValueError("Onshape URL is not accessible")
            await self.edit_listing(
                listing_id=listing_id,
                onshape_url=onshape_url,
            )

    async def download_onshape_document(
        self,
        listing: Listing,
        onshape_url: str,
        *,
        config: ConverterConfig | None = None,
    ) -> AsyncIterable[str]:
        if config is None:
            config = ConverterConfig()

        queue: asyncio.Queue[tuple[str, MessageLevel] | None] = asyncio.Queue()

        async def get_thumbnail(api: OnshapeApi, onshape_url: str, listing: Listing, queue: asyncio.Queue) -> None:
            try:
                document = api.parse_url(onshape_url)
                out_file = io.BytesIO()
                await api.download_thumbnail(out_file, document)
                out_file.seek(0)
                image = Image.open(out_file)
                image_artifact = await self._upload_image("thumbnail.png", image, listing)
                await queue.put((image_artifact.id, "image"))
            except Exception as e:
                await queue.put((f"Failed to get thumbnail: {str(e)}", "error"))

        async def get_urdf(
            onshape_url: str,
            temp_dir: str,
            listing: Listing,
            config: ConverterConfig,
            queue: asyncio.Queue,
        ) -> None:
            try:
                document_info = await download(onshape_url, temp_dir, config=config)
                await queue.put(("Downloading complete", "success"))
                postprocess_info = await postprocess(document_info.urdf_info.urdf_path, config=config)
                tar_path = postprocess_info.tar_path
                await queue.put(("Postprocessing complete", "success"))

                buffer = io.BytesIO()
                with open(tar_path, "rb") as f:
                    buffer.write(f.read())
                buffer.seek(0)

                new_artifact = await self._upload_and_store(
                    name=tar_path.name,
                    file=buffer,
                    listing=listing,
                    artifact_type="tgz",
                    description=f"Generated from {onshape_url}",
                )
                await queue.put((new_artifact.id, "urdf"))
            except Exception as e:
                await queue.put((f"Failed to get URDF: {str(e)}", "error"))
                await queue.put(
                    (
                        "\n".join(
                            [
                                "If you think this was an error, please file an issue:",
                                "  https://github.com/kscalelabs/onshape",
                                "To reproduce locally, run:",
                                "  pip install kscale-onshape-library",
                                f"  kol run '{onshape_url}'",
                            ]
                        ),
                        "error",
                    )
                )

        async def worker(onshape_url: str, listing: Listing, config: ConverterConfig, queue: asyncio.Queue) -> None:
            with tempfile.TemporaryDirectory() as temp_dir, capture_logs(queue, "kol"), capture_logs(queue, "httpx"):
                try:
                    api = OnshapeApi(OnshapeClient())

                    # Run both tasks concurrently
                    await asyncio.gather(
                        get_thumbnail(api, onshape_url, listing, queue),
                        get_urdf(onshape_url, temp_dir, listing, config, queue),
                    )
                finally:
                    await queue.put(None)

        async def worker_with_timeout() -> None:
            await asyncio.wait_for(worker(onshape_url, listing, config, queue), timeout=300)
            while not queue.empty():
                await queue.get()
            await queue.put(None)

        # Yield messages from the queue until the worker task is done.
        worker_task = asyncio.create_task(worker_with_timeout())
        while (sample := await queue.get()) is not None:
            message, level = sample
            message_lines = [m for m in message.split("\n") if m.strip()]

            # Send a different event type for image and URDF IDs.
            match level:
                case "error":
                    event_type = "message"
                case "info":
                    event_type = "message"
                case "success":
                    event_type = "message"
                case "image":
                    event_type = "image"
                    level = "success"
                case "urdf":
                    event_type = "urdf"
                    level = "success"
                case _:
                    event_type = "message"

            for message_line in message_lines[::-1]:
                yield f"event: {event_type}\ndata: {json.dumps({'message': message_line, 'level': level})}\n\n"

        await worker_task


async def test_adhoc() -> None:
    parser = argparse.ArgumentParser(description="Onshape CRUD operations")
    parser.add_argument("onshape_url", help="The URL of the Onshape document")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    async with OnshapeCrud() as crud:
        document_exists = await crud.onshape_document_exists(args.onshape_url)
        logger.info("Document exists: %s", document_exists)


if __name__ == "__main__":
    # python -m store.app.crud.onshape
    asyncio.run(test_adhoc())
