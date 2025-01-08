"""This module provides a class to generate signed URLs for AWS CloudFront using RSA keys.

The `CloudFrontUrlSigner` class allows you to create and sign CloudFront URLs with optional custom policies.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Optional, Self

from botocore.signers import CloudFrontSigner
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from www.settings import env


class CloudFrontUrlSigner:
    """A class to generate signed URLs for AWS CloudFront using RSA keys."""

    def __init__(self, key_id: str, private_key: str) -> None:
        """Initialize the CloudFrontUrlSigner with a key ID and private key content.

        :param key_id: The CloudFront key ID associated with the public key in your CloudFront key group.
        :param private_key: The private key content in PEM format.
        """
        self.key_id = key_id
        self.private_key = private_key
        self.cf_signer = CloudFrontSigner(key_id, self._rsa_signer)

    def _rsa_signer(self, message: bytes) -> bytes:
        """RSA signer function that signs a message using the private key.

        Args:
            message: The message to be signed.

        Returns:
            bytes: The RSA signature of the message.

        Raises:
            ValueError: If the loaded key is not an RSA private key.
        """
        private_key = serialization.load_pem_private_key(
            self.private_key.encode("utf-8"),
            password=None,
        )

        if not isinstance(private_key, RSAPrivateKey):
            raise ValueError("The provided key is not an RSA private key")

        return private_key.sign(message, padding.PKCS1v15(), hashes.SHA1())

    def generate_presigned_url(self, url: str, policy: Optional[str] = None) -> str:
        """Generate a presigned URL for CloudFront using an optional custom policy.

        :param url: The URL to sign.
        :param policy: (Optional) A custom policy for the URL.
        :return: The signed URL.
        """
        return self.cf_signer.generate_presigned_url(url, policy=policy)

    def create_custom_policy(self, url: str, expire_days: float = 1, ip_range: Optional[str] = None) -> str:
        """Create a custom policy for CloudFront signed URLs.

        :param url: The URL to be signed.
        :param expire_days: Number of days until the policy expires (can be fractional, e.g., 1/24 for one hour).
        :param ip_range: Optional IP range to restrict access (e.g., "203.0.113.0/24").
        :return: The custom policy in JSON format.
        """
        expiration_time = int((datetime.utcnow() + timedelta(days=expire_days)).timestamp())
        policy: dict[str, Any] = {
            "Statement": [
                {
                    "Resource": url,
                    "Condition": {
                        "DateLessThan": {"AWS:EpochTime": expiration_time},
                    },
                }
            ]
        }
        if ip_range:
            policy["Statement"][0]["Condition"]["IpAddress"] = {"AWS:SourceIp": ip_range}

        return json.dumps(policy, separators=(",", ":"))

    @classmethod
    def get(cls) -> Self:
        return cls(
            key_id=env.aws.cloudfront.key_id,
            private_key=env.aws.cloudfront.private_key,
        )
