"""Defines the bot environment settings."""

from dataclasses import dataclass, field

from omegaconf import II, MISSING, SI


@dataclass
class MiddlewareSettings:
    secret_key: str = field(default=II("oc.env:MIDDLEWARE_SECRET_KEY"))


@dataclass
class OauthSettings:
    cognito_authority: str = field(default=II("oc.env:COGNITO_AUTHORITY"))
    cognito_client_id: str = field(default=II("oc.env:COGNITO_CLIENT_ID"))
    cognito_client_secret: str = field(default=II("oc.env:COGNITO_CLIENT_SECRET"))
    cognito_redirect_uri: str = field(default=MISSING)
    cognito_uri: str = field(default="https://auth.kscale.dev")
    authorization_url: str = field(default=SI("${oauth.cognito_uri}/oauth2/authorize"))
    client_id: str = field(default="www-api")
    token_url: str = field(default=SI("${oauth.cognito_uri}/oauth2/token"))
    jwks_url: str = field(default=SI("${oauth.cognito_authority}/.well-known/jwks.json"))
    server_metadata_url: str = field(default=SI("${oauth.cognito_authority}/.well-known/openid-configuration"))
    permitted_jwt_audiences: list[str] = field(default_factory=lambda: ["account"])


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
class S3Settings:
    bucket: str = field(default=II("oc.env:S3_BUCKET"))
    prefix: str = field(default=II("oc.env:S3_PREFIX"))


@dataclass
class DynamoSettings:
    table_name: str = field(default=MISSING)


@dataclass
class SiteSettings:
    homepage: str = field(default=MISSING)
    artifact_base_url: str = field(default=MISSING)
    enable_test_endpoint: bool = field(default=False)


@dataclass
class CloudFrontSettings:
    domain: str = field(default=II("oc.env:CLOUDFRONT_DOMAIN"))
    key_id: str | None = field(default=II("oc.env:CLOUDFRONT_KEY_ID"))
    private_key: str | None = field(default=II("oc.env:CLOUDFRONT_PRIVATE_KEY"))


@dataclass
class EnvironmentSettings:
    middleware: MiddlewareSettings = field(default_factory=MiddlewareSettings)
    oauth: OauthSettings = field(default_factory=OauthSettings)
    user: UserSettings = field(default_factory=UserSettings)
    crypto: CryptoSettings = field(default_factory=CryptoSettings)
    email: EmailSettings = field(default_factory=EmailSettings)
    artifact: ArtifactSettings = field(default_factory=ArtifactSettings)
    s3: S3Settings = field(default_factory=S3Settings)
    dynamo: DynamoSettings = field(default_factory=DynamoSettings)
    site: SiteSettings = field(default_factory=SiteSettings)
    cloudfront: CloudFrontSettings = field(default_factory=CloudFrontSettings)
    debug: bool = field(default=False)
    environment: str = field(default="local")
