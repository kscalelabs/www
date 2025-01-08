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

from www.crud.cloudfront import create_cloudfront_distribution
from www.crud.s3 import create_s3_bucket

logger = logging.getLogger(__name__)


async def main() -> None:
    colorlogging.configure()

    parser = argparse.ArgumentParser()
    parser.add_argument("--s3", action="store_true", help="Create the S3 bucket.")
    parser.add_argument("--cf", action="store_true", help="Create the Cloudfront distribution.")
    args = parser.parse_args()

    if args.s3:
        logger.info("Creating S3 bucket...")
        await create_s3_bucket()

    if args.cf:
        logger.info("Creating Cloudfront distribution...")
        await create_cloudfront_distribution()


if __name__ == "__main__":
    asyncio.run(main())
