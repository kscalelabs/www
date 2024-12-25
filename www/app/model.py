"""Defines the table models for the API.

These correspond directly with the rows in our database, and provide helper
methods for converting from our input data into the format the database
expects (for example, converting a UUID into a string).
"""

import time
from datetime import datetime, timedelta
from typing import Literal, Self, cast, get_args

from pydantic import BaseModel, field_validator

from www.app.errors import InternalError
from www.app.utils.password import hash_password
from www.settings import settings
from www.utils import new_uuid


class StoreBaseModel(BaseModel):
    """Defines the base model for store database rows.

    Our database architecture uses a single table with a single primary key
    (the `id` field). This class provides a common interface for all models
    that are stored in the database.
    """

    id: str


UserPermission = Literal["is_admin", "is_mod", "is_content_manager", "is_verified_member"]


class User(StoreBaseModel):
    """Defines the user model for the API.

    Users are defined by their id, email, and username (all unique).
    Hashed password is set if user signs up with email and password, and is
    left empty if the user signed up with Google or Github OAuth.
    """

    email: str
    username: str
    hashed_password: str | None = None
    permissions: set[UserPermission] | None = None
    created_at: int
    updated_at: int
    github_id: str | None = None
    google_id: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    name: str | None = None
    bio: str | None = None

    @classmethod
    def create(
        cls,
        email: str,
        username: str,
        password: str | None = None,
        github_id: str | None = None,
        google_id: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        name: str | None = None,
        bio: str | None = None,
    ) -> Self:
        now = int(time.time())
        hashed_pw = hash_password(password) if password else None
        return cls(
            id=new_uuid(),
            email=email,
            username=username,
            hashed_password=hashed_pw,
            created_at=now,
            updated_at=now,
            github_id=github_id,
            google_id=google_id,
            first_name=first_name,
            last_name=last_name,
            name=name,
            bio=bio,
        )

    def update_timestamp(self) -> None:
        self.updated_at = int(time.time())

    def verify_email(self) -> None:
        self.email_verified_at = int(time.time())

    def set_username(self, new_username: str) -> None:
        self.username = new_username
        self.update_timestamp()


class OAuthKey(StoreBaseModel):
    """Keys for OAuth providers which identify users."""

    user_id: str
    provider: str
    user_token: str

    @classmethod
    def create(cls, user_id: str, provider: str, user_token: str) -> Self:
        return cls(id=new_uuid(), user_id=user_id, provider=provider, user_token=user_token)


APIKeySource = Literal["user", "oauth", "password"]
APIKeyPermission = Literal["read", "write", "admin"]
APIKeyPermissionSet = set[APIKeyPermission] | Literal["full", None]


class APIKey(StoreBaseModel):
    """The API key is used for querying the API.

    Downstream users keep the API key, and it is used to authenticate
    requests to the API. The key is stored in the database, and can be
    revoked by the user at any time.
    """

    user_id: str
    source: APIKeySource
    permissions: set[APIKeyPermission] | None = None
    ttl: int | None = None
    created_at: int

    @field_validator("permissions", mode="before")
    @classmethod
    def convert_permissions_to_set(
        cls, v: list[APIKeyPermission] | set[APIKeyPermission] | None
    ) -> set[APIKeyPermission] | None:
        if isinstance(v, list):
            return set(v)
        return v

    @classmethod
    def create(cls, user_id: str, source: APIKeySource, permissions: APIKeyPermissionSet) -> Self:
        if permissions == "full":
            permissions = {"read", "write", "admin"}
        ttl_timestamp = int((datetime.utcnow() + timedelta(days=90)).timestamp())
        return cls(
            id=new_uuid(),
            user_id=user_id,
            source=source,
            permissions=permissions,
            ttl=ttl_timestamp,
            created_at=int(time.time()),
        )


ArtifactSize = Literal["small", "large"]

ImageArtifactType = Literal["image"]
XMLArtifactType = Literal["urdf", "mjcf"]
MeshArtifactType = Literal["stl", "obj", "dae", "ply"]
CompressedArtifactType = Literal["tgz", "zip"]
KernelArtifactType = Literal["kernel"]
ArtifactType = ImageArtifactType | KernelArtifactType | XMLArtifactType | MeshArtifactType | CompressedArtifactType

UPLOAD_CONTENT_TYPE_OPTIONS: dict[ArtifactType, set[str]] = {
    # Image
    "image": {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"},
    # XML
    "urdf": {"application/octet-stream", "text/xml", "application/xml"},
    "mjcf": {"application/octet-stream", "text/xml", "application/xml"},
    # Meshes
    "stl": {"application/octet-stream", "text/plain"},
    "obj": {"application/octet-stream", "text/plain"},
    "dae": {"application/octet-stream", "text/plain"},
    "ply": {"application/octet-stream", "text/plain"},
    # Compressed
    "tgz": {
        "application/gzip",
        "application/x-gzip",
        "application/x-tar",
        "application/x-compressed-tar",
    },
    "zip": {"application/zip"},
}

DOWNLOAD_CONTENT_TYPE: dict[ArtifactType, str] = {
    # Image
    "image": "image/png",
    # XML
    "urdf": "application/octet-stream",
    "mjcf": "application/octet-stream",
    # Binary
    "stl": "application/octet-stream",
    "obj": "application/octet-stream",
    "dae": "application/octet-stream",
    "ply": "application/octet-stream",
    # Compressed
    "tgz": "application/gzip",
    "zip": "application/zip",
    "kernel": "application/octet-stream",
}

SizeMapping: dict[ArtifactSize, tuple[int, int]] = {
    "large": settings.artifact.large_image_size,
    "small": settings.artifact.small_image_size,
}


def get_artifact_type(content_type: str | None, filename: str | None) -> ArtifactType:
    if filename is not None:
        extension = filename.split(".")[-1].lower()
        if extension == "img":
            return "kernel"
        if extension in ("png", "jpeg", "jpg", "gif", "webp"):
            return "image"
        if extension in ("urdf",):
            return "urdf"
        if extension in ("mjcf", "xml"):
            return "mjcf"
        if extension in ("stl",):
            return "stl"
        if extension in ("obj",):
            return "obj"
        if extension in ("dae",):
            return "dae"
        if extension in ("ply",):
            return "ply"
        if extension in ("tgz", "tar.gz"):
            return "tgz"
        if extension in ("zip",):
            return "zip"

    # Attempts to determine from content type.
    if content_type is not None:
        if content_type in UPLOAD_CONTENT_TYPE_OPTIONS["kernel"]:
            return "kernel"
        if content_type in UPLOAD_CONTENT_TYPE_OPTIONS["image"]:
            return "image"
        if content_type in UPLOAD_CONTENT_TYPE_OPTIONS["urdf"]:
            return "urdf"
        if content_type in UPLOAD_CONTENT_TYPE_OPTIONS["mjcf"]:
            return "mjcf"
        if content_type in UPLOAD_CONTENT_TYPE_OPTIONS["stl"]:
            return "stl"
        if content_type in UPLOAD_CONTENT_TYPE_OPTIONS["obj"]:
            return "obj"
        if content_type in UPLOAD_CONTENT_TYPE_OPTIONS["dae"]:
            return "dae"
        if content_type in UPLOAD_CONTENT_TYPE_OPTIONS["ply"]:
            return "ply"
        if content_type in UPLOAD_CONTENT_TYPE_OPTIONS["tgz"]:
            return "tgz"
        if content_type in UPLOAD_CONTENT_TYPE_OPTIONS["zip"]:
            return "zip"

    raise ValueError(f"Unknown content type for file: {filename}")


def get_compression_type(content_type: str | None, filename: str | None) -> CompressedArtifactType:
    if filename is None:
        raise ValueError("Filename must be provided")

    artifact_type = get_artifact_type(content_type, filename)
    if artifact_type not in (allowed_types := get_args(CompressedArtifactType)):
        raise ValueError(f"Artifact type {artifact_type} is not compressed; expected one of {allowed_types}")
    return cast(CompressedArtifactType, artifact_type)


def check_content_type(content_type: str | None, artifact_type: ArtifactType) -> None:
    """Checks that the content type is valid for the artifact type.

    Args:
        content_type: The content type of the artifact.
        artifact_type: The type of the artifact.

    Raises:
        ValueError: If the content type is not valid for the artifact type.
    """
    if content_type is None:
        raise ValueError("Artifact content type was not provided")
    if content_type not in UPLOAD_CONTENT_TYPE_OPTIONS[artifact_type]:
        content_type_options_string = ", ".join(UPLOAD_CONTENT_TYPE_OPTIONS[artifact_type])
        raise ValueError(f"Invalid content type for artifact; {content_type} not in [{content_type_options_string}]")


def get_content_type(artifact_type: ArtifactType) -> str:
    return DOWNLOAD_CONTENT_TYPE[artifact_type]


class Artifact(StoreBaseModel):
    """Defines an artifact that some user owns, like an image or uploaded file.

    Artifacts are stored in S3 and are accessible through CloudFront.

    Artifacts are associated to a given user and can come in different sizes;
    for example, the same image may have multiple possible sizes available.
    """

    user_id: str
    listing_id: str
    name: str
    artifact_type: ArtifactType
    sizes: list[ArtifactSize] | None = None
    description: str | None = None
    timestamp: int
    children: list[str] | None = None
    is_main: bool = False

    @classmethod
    def create(
        cls,
        user_id: str,
        listing_id: str,
        name: str,
        artifact_type: ArtifactType,
        sizes: list[ArtifactSize] | None = None,
        description: str | None = None,
        children: list[str] | None = None,
        is_main: bool = False,
    ) -> Self:
        return cls(
            id=new_uuid(),
            user_id=user_id,
            listing_id=listing_id,
            name=name,
            artifact_type=artifact_type,
            sizes=sizes,
            description=description,
            timestamp=int(time.time()),
            children=children,
            is_main=is_main,
        )


class Listing(StoreBaseModel):
    """Defines a recursively-defined listing.

    Listings can have sub-listings with their component parts. They can also
    have associated user-uploaded artifacts like images and URDFs.
    """

    user_id: str
    created_at: int
    updated_at: int
    name: str
    slug: str
    child_ids: list[str]
    description: str | None = None
    onshape_url: str | None = None
    views: int = 0
    score: int = 0

    @classmethod
    def create(
        cls,
        user_id: str,
        name: str,
        slug: str,
        child_ids: list[str],
        description: str | None = None,
        onshape_url: str | None = None,
    ) -> Self:
        return cls(
            id=new_uuid(),
            user_id=user_id,
            created_at=int(time.time()),
            updated_at=int(time.time()),
            name=name,
            slug=slug,
            child_ids=child_ids,
            description=description,
            onshape_url=onshape_url,
            views=0,
            score=0,
        )


class ListingTag(StoreBaseModel):
    """Marks a listing as having a given tag.

    This is useful for tagging listings with metadata, like "robot", "gripper",
    or "actuator". Tags are used to categorize listings and make them easier to
    search for.
    """

    listing_id: str
    name: str

    @classmethod
    def create(cls, listing_id: str, tag: str) -> Self:
        return cls(
            id=new_uuid(),
            listing_id=listing_id,
            name=tag,
        )


def get_artifact_name(
    *,
    artifact: Artifact | None = None,
    artifact_id: str | None = None,
    listing_id: str | None = None,
    name: str | None = None,
    artifact_type: ArtifactType | None = None,
    size: ArtifactSize = "large",
) -> str:
    if artifact:
        listing_id = artifact.listing_id
        name = artifact.name
        artifact_type = artifact.artifact_type
        artifact_id = artifact.id
    elif not listing_id or not name or not artifact_type or not artifact_id:
        raise InternalError("Must provide artifact or listing_id, name, and artifact_type")

    match artifact_type:
        case "image":
            height, width = SizeMapping[size]
            return f"{listing_id}/{artifact_id}/{size}_{height}x{width}_{name}"
        case "kernel" | "urdf" | "mjcf" | "stl" | "obj" | "ply" | "dae" | "zip" | "tgz":
            return f"{listing_id}/{artifact_id}/{name}"
        case _:
            raise ValueError(f"Unknown artifact type: {artifact_type}")


def get_artifact_url(
    *,
    artifact: Artifact | None = None,
    artifact_id: str | None = None,
    artifact_type: ArtifactType | None = None,
    listing_id: str | None = None,
    name: str | None = None,
    size: ArtifactSize = "large",
) -> str:
    artifact_name = get_artifact_name(
        artifact=artifact,
        artifact_id=artifact_id,
        listing_id=listing_id,
        name=name,
        artifact_type=artifact_type,
        size=size,
    )
    return f"{settings.site.artifact_base_url}{artifact_name}"


def get_artifact_urls(
    artifact: Artifact | None = None,
    artifact_type: ArtifactType | None = None,
    listing_id: str | None = None,
    name: str | None = None,
) -> dict[ArtifactSize, str]:
    return {
        size: get_artifact_url(
            artifact=artifact,
            artifact_type=artifact_type,
            listing_id=listing_id,
            name=name,
            size=size,
        )
        for size in SizeMapping.keys()
    }


async def can_write_artifact(user: User, artifact: Artifact) -> bool:
    if user.permissions is not None and "is_admin" in user.permissions:
        return True
    if user.id == artifact.user_id:
        return True
    return False


async def can_write_listing(user: User, listing: Listing) -> bool:
    if user.permissions is not None and ("is_admin" in user.permissions or "is_mod" in user.permissions):
        return True
    if user.id == listing.user_id:
        return True
    return False


async def can_read_artifact(user: User, artifact: Artifact) -> bool:
    # For now, all users can read all artifacts. In the future we might change
    # this so that users can hide their artifacts.
    return True


async def can_read_listing(user: User, listing: Listing) -> bool:
    # For now, all users can read all listings. In the future we might change
    # this so that users can hide their listings.
    return True


class ListingVote(StoreBaseModel):
    """Tracks user votes on listings."""

    user_id: str
    listing_id: str
    is_upvote: bool
    created_at: int

    @classmethod
    def create(cls, user_id: str, listing_id: str, is_upvote: bool) -> Self:
        return cls(
            id=new_uuid(),
            user_id=user_id,
            listing_id=listing_id,
            is_upvote=is_upvote,
            created_at=int(time.time()),
        )


class Robot(StoreBaseModel):
    """User registered robots. Associated with a robot listing.

    Will eventually used for teleop and data collection/aggregation.
    """

    user_id: str
    listing_id: str
    name: str
    description: str | None = None
    created_at: int
    updated_at: int
    order_id: str | None = None

    @classmethod
    def create(
        cls,
        user_id: str,
        listing_id: str,
        name: str,
        description: str | None = None,
        order_id: str | None = None,
    ) -> Self:
        now = int(time.time())
        return cls(
            id=new_uuid(),
            user_id=user_id,
            listing_id=listing_id,
            name=name,
            description=description,
            created_at=now,
            updated_at=now,
            order_id=order_id,
        )


class TeleopICECandidate(StoreBaseModel):
    """Tracks ICE candidates for teleoperation."""

    user_id: str
    robot_id: str
    candidate: str
    created_at: int
    ttl: int | None = None

    @classmethod
    def create(
        cls,
        user_id: str,
        robot_id: str,
        candidate: str,
        expire_after_n_hours: int = 24,
    ) -> Self:
        now = int(time.time())
        ttl_timestamp = int((datetime.utcnow() + timedelta(hours=expire_after_n_hours)).timestamp())
        return cls(
            id=new_uuid(),
            user_id=user_id,
            robot_id=robot_id,
            candidate=candidate,
            created_at=now,
            ttl=ttl_timestamp,
        )


class KRec(StoreBaseModel):
    """Krec recorded from robot runtime."""

    user_id: str
    robot_id: str
    created_at: int
    name: str
    description: str | None = None

    @classmethod
    def create(
        cls,
        user_id: str,
        robot_id: str,
        name: str,
        description: str | None = None,
    ) -> Self:
        now = int(time.time())
        return cls(
            id=new_uuid(),
            user_id=user_id,
            robot_id=robot_id,
            created_at=now,
            name=name,
            description=description,
        )
