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

from www.crud.base.db import DBCrud
from www.crud.base.s3 import create_s3_bucket
from www.crud.robot import robot_crud
from www.crud.robot_class import robot_class_crud

logger = logging.getLogger(__name__)

CRUDS: list[DBCrud] = [robot_class_crud, robot_crud]


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
        for crud in CRUDS:
            async with crud:
                logger.info("Creating %s table...", crud.table_name)
                await crud.create_table()


if __name__ == "__main__":
    asyncio.run(main())
