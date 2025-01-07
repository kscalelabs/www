"""Defines some common utility functions for the database."""

import datetime
import hashlib
import uuid


def server_time() -> datetime.datetime:
    return datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)


def new_uuid() -> str:
    """Generate a new UUID.

    Returns:
        A new UUID, as a string, with the first 16 characters of the
        SHA-256 hash of a UUID4 value.
    """
    return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:16]
