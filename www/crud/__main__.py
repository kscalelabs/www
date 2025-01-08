"""Runs the CRUD creation functions."""

import asyncio

import colorlogging

from . import create

if __name__ == "__main__":
    # python -m www.crud
    colorlogging.configure()
    asyncio.run(create())
