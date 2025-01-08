"""Defines the script to create the database.

This script is meant to be run locally, to create the initial database tables
in localstack. To run it, use:

```bash
python -m scripts.create_db --s3
```
"""

import argparse
import asyncio
import logging

import colorlogging

from www.crud.db import create_dbs
from www.crud.s3 import create_s3_bucket

logger = logging.getLogger(__name__)


async def main() -> None:
    colorlogging.configure()

    parser = argparse.ArgumentParser()
    parser.add_argument("--s3", action="store_true", help="Create the S3 bucket.")
    parser.add_argument("--db", action="store_true", help="Create the DynamoDB tables.")
    args = parser.parse_args()

    if args.s3:
        logger.info("Creating S3 bucket...")
        await create_s3_bucket()

    if args.db:
        logger.info("Creating DynamoDB tables...")
        await create_dbs()


if __name__ == "__main__":
    asyncio.run(main())
