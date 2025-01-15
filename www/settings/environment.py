"""Defines the bot environment settings."""

from dataclasses import dataclass, field

from omegaconf import II, MISSING, SI


@dataclass
class MiddlewareSettings:
    secret_key: str = field(default=II("oc.env:MIDDLEWARE_SECRET_KEY"))


@dataclass
class CryptoSettings:
    cache_token_db_result_seconds: int = field(default=30)
    expire_otp_minutes: int = field(default=10)
    algorithm: str = field(default="HS256")


@dataclass
class UserSettings:
    authorized_emails: list[str] | None = field(default=None)
    admin_emails: list[str] = field(default_factory=lambda: [])


@dataclass
class EmailSettings:
    host: str = field(default=II("oc.env:SMTP_HOST"))
    port: int = field(default=587)
    username: str = field(default=II("oc.env:SMTP_USERNAME"))
    password: str = field(default=II("oc.env:SMTP_PASSWORD"))
    sender_email: str = field(default=II("oc.env:SMTP_SENDER_EMAIL"))
    sender_name: str = field(default=II("oc.env:SMTP_SENDER_NAME"))


@dataclass
class ArtifactSettings:
    large_image_size: tuple[int, int] = field(default=(1536, 1536))
    small_image_size: tuple[int, int] = field(default=(256, 256))
    min_bytes: int = field(default=16)
    max_bytes: int = field(default=1536 * 1536 * 25)
    quality: int = field(default=80)
    max_concurrent_file_uploads: int = field(default=3)


@dataclass
class DynamoSettings:
    table_prefix: str = field(default=SI("www-${environment}"))
    deletion_protection: bool = field(default=False)


@dataclass
class S3Settings:
    bucket: str = field(default=SI("kscale-www-${environment}"))
    prefix: str = field(default="")


@dataclass
class CloudFrontSettings:
    domain: str = field(default=II("oc.env:CLOUDFRONT_DOMAIN"))
    key_id: str = field(default=II("oc.env:CLOUDFRONT_KEY_ID"))
    private_key: str = field(default=II("oc.env:CLOUDFRONT_PRIVATE_KEY"))


@dataclass
class AwsSettings:
    dynamodb: DynamoSettings = field(default_factory=DynamoSettings)
    s3: S3Settings = field(default_factory=S3Settings)
    cloudfront: CloudFrontSettings = field(default_factory=CloudFrontSettings)


@dataclass
class SiteSettings:
    homepage: str = field(default=MISSING)
    artifact_base_url: str = field(default=MISSING)
    is_test_environment: bool = field(default=False)


@dataclass
class EnvironmentSettings:
    middleware: MiddlewareSettings = field(default_factory=MiddlewareSettings)
    user: UserSettings = field(default_factory=UserSettings)
    crypto: CryptoSettings = field(default_factory=CryptoSettings)
    email: EmailSettings = field(default_factory=EmailSettings)
    artifact: ArtifactSettings = field(default_factory=ArtifactSettings)
    aws: AwsSettings = field(default_factory=AwsSettings)
    site: SiteSettings = field(default_factory=SiteSettings)
    debug: bool = field(default=False)
    environment: str = field(default="local")
