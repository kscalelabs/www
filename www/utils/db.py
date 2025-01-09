"""Defines some common utility functions for the database."""

import datetime
import hashlib
import re
import uuid
from dataclasses import dataclass


def server_time() -> datetime.datetime:
    return datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)


def new_uuid() -> str:
    """Generate a new UUID.

    Returns:
        A new UUID, as a string, with the first 16 characters of the
        SHA-256 hash of a UUID4 value.
    """
    return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:16]


@dataclass
class VersionNumber:
    major: int
    minor: int
    patch: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    def __lt__(self, other: "VersionNumber") -> bool:
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other: "VersionNumber") -> bool:
        return (self.major, self.minor, self.patch) <= (other.major, other.minor, other.patch)

    def __gt__(self, other: "VersionNumber") -> bool:
        return (self.major, self.minor, self.patch) > (other.major, other.minor, other.patch)

    def __ge__(self, other: "VersionNumber") -> bool:
        return (self.major, self.minor, self.patch) >= (other.major, other.minor, other.patch)

    def __eq__(self, other: "VersionNumber") -> bool:
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

    def __ne__(self, other: "VersionNumber") -> bool:
        return (self.major, self.minor, self.patch) != (other.major, other.minor, other.patch)

    def __repr__(self) -> str:
        return f"VersionNumber(major={self.major}, minor={self.minor}, patch={self.patch})"

    @classmethod
    def from_str(cls, version: str) -> "VersionNumber":
        match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
        if match is None:
            raise ValueError(f"Invalid version number: {version}")
        return cls(major=int(match.group(1)), minor=int(match.group(2)), patch=int(match.group(3)))
