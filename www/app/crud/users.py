"""Defines CRUD interface for user API."""

import asyncio
import logging
import random
import string
import warnings
from typing import Any, Literal, Optional, overload

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from pydantic import BaseModel

from www.app.crud.base import TABLE_NAME, BaseCrud
from www.app.crud.listings import ListingsCrud
from www.app.model import (
    APIKey,
    APIKeyPermissionSet,
    APIKeySource,
    OAuthKey,
    User,
)
from www.app.utils.email import send_signup_notification_email
from www.settings import settings
from www.utils import cache_async_result

logger = logging.getLogger(__name__)


class UserNotFoundError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class UserPublic(BaseModel):
    """Defines public user model for frontend.

    Omits private/sesnsitive user fields. Is the return type for
    retrieving user data on frontend (for public profile pages, etc).
    """

    id: str
    email: str
    username: str
    created_at: int
    updated_at: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    name: str | None = None
    bio: str | None = None


class UserCrud(BaseCrud):
    @classmethod
    def get_gsis(cls) -> set[str]:
        return super().get_gsis().union({"user_id", "email", "user_token", "username"})

    @overload
    async def get_user(self, id: str, throw_if_missing: Literal[True]) -> User: ...

    @overload
    async def get_user(self, id: str, throw_if_missing: bool = False) -> User | None: ...

    async def get_user(self, id: str, throw_if_missing: bool = False) -> User | None:
        return await self._get_item(id, User, throw_if_missing=throw_if_missing)

    @overload
    async def get_user_public(self, id: str, throw_if_missing: Literal[True]) -> UserPublic: ...

    @overload
    async def get_user_public(self, id: str, throw_if_missing: bool = False) -> UserPublic | None: ...

    async def get_user_public(self, id: str, throw_if_missing: bool = False) -> UserPublic | None:
        user = await self.get_user(id, throw_if_missing=throw_if_missing)
        if user is None:
            if throw_if_missing:
                raise UserNotFoundError(f"User with id {id} not found")
            return None
        return UserPublic(**user.model_dump())

    async def _create_user_from_email(self, email: str, password: str) -> User:
        try:
            base_username = email.split("@")[0]
            unique_username = await self.generate_unique_username(base_username)
            user = User.create(email=email, username=unique_username, password=password)
            await self._add_item(user, unique_fields=["email", "username"])
            return user
        except Exception as e:
            logger.exception("Error in _create_user_from_email: %s", e)
            raise

    async def _create_user_from_oauth(
        self,
        email: str,
        provider: str,
        user_token: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> User:
        try:
            user = await self.get_user_from_email(email)
            if user is None:
                # Generate a unique username based on the email
                base_username = email.split("@")[0]
                unique_username = await self.generate_unique_username(base_username)

                user = User.create(
                    email=email, username=unique_username, first_name=first_name, last_name=last_name, password=None
                )
                if provider == "github":
                    user.github_id = user_token
                elif provider == "google":
                    user.google_id = user_token
                await self._add_item(user, unique_fields=["email", "username"])
                await send_signup_notification_email(email)
            elif provider == "github":
                await self._update_item(user.id, User, {"github_id": user_token})
            elif provider == "google":
                await self._update_item(user.id, User, {"google_id": user_token})

            oauth_key = OAuthKey.create(user_id=user.id, provider=provider, user_token=user_token)
            await self._add_item(oauth_key, unique_fields=["user_token"])

            return user
        except Exception as e:
            logger.exception("Error in _create_user_from_oauth: %s", e)
            raise

    @overload
    async def _get_oauth_key(self, token: str, throw_if_missing: Literal[True]) -> OAuthKey: ...

    @overload
    async def _get_oauth_key(self, token: str, throw_if_missing: bool = False) -> OAuthKey | None: ...

    async def _get_oauth_key(self, token: str, throw_if_missing: bool = False) -> OAuthKey | None:
        return await self._get_unique_item_from_secondary_index(
            "user_token",
            token,
            OAuthKey,
            throw_if_missing=throw_if_missing,
        )

    async def _get_user_from_auth_key(self, token: str) -> User | None:
        key = await self._get_oauth_key(token)
        return None if key is None else await self.get_user(key.user_id)

    async def get_user_from_github_token(self, token: str, email: str) -> User:
        try:
            auth_key = github_auth_key(token)
            user = await self._get_user_from_auth_key(auth_key)
            if user is not None:
                return user
            return await self._create_user_from_oauth(email, "github", auth_key)
        except Exception as e:
            logger.exception("Error in get_user_from_github_token: %s", e)
            raise

    async def delete_github_token(self, github_id: str) -> None:
        await self._delete_item(await self._get_oauth_key(github_auth_key(github_id), throw_if_missing=True))

    async def get_user_from_google_token(
        self,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> User:
        try:
            auth_key = google_auth_key(email)
            user = await self._get_user_from_auth_key(auth_key)
            if user is not None:
                return user
            return await self._create_user_from_oauth(email, "google", auth_key, first_name, last_name)
        except Exception as e:
            logger.exception("Error in get_user_from_google_token: %s", e)
            raise

    async def delete_google_token(self, google_id: str) -> None:
        await self._delete_item(await self._get_oauth_key(google_auth_key(google_id), throw_if_missing=True))

    async def get_user_from_email(self, email: str) -> User | None:
        return await self._get_unique_item_from_secondary_index("email", email, User)

    async def get_user_batch(self, ids: list[str]) -> list[User]:
        return await self._get_item_batch(ids, User)

    async def get_user_from_api_key(self, api_key_id: str) -> User:
        api_key = await self.get_api_key(api_key_id)
        return await self._get_item(api_key.user_id, User, throw_if_missing=True)

    async def delete_user(self, id: str) -> None:
        async def delete_api_keys() -> None:
            api_keys = await self.list_api_keys(id)
            await asyncio.gather(*[self.delete_api_key(key) for key in api_keys])

        async def delete_oauth_keys() -> None:
            oauth_keys = await self._get_items_from_secondary_index("user_id", id, OAuthKey)
            await asyncio.gather(*[self._delete_item(key) for key in oauth_keys])

        # Delete the user's API keys and OAuth keys.
        await asyncio.gather(delete_api_keys(), delete_oauth_keys())

        # Delete the user itself.
        await self._delete_item(id)

    async def list_users(self) -> list[User]:
        warnings.warn("`list_users` probably shouldn't be called in production", ResourceWarning)
        return await self._list_items(User)

    async def get_user_count(self) -> int:
        return await self._count_items(User)

    @cache_async_result(settings.crypto.cache_token_db_result_seconds)
    async def get_api_key(self, api_key_id: str) -> APIKey:
        return await self._get_item(api_key_id, APIKey, throw_if_missing=True)

    async def add_api_key(
        self,
        user_id: str,
        source: APIKeySource,
        permissions: APIKeyPermissionSet,
    ) -> APIKey:
        user_api_keys = await self.list_api_keys(user_id)
        if len(user_api_keys) >= 10:
            await asyncio.gather(*[self.delete_api_key(key.id) for key in user_api_keys[:-10]])
        api_key = APIKey.create(user_id=user_id, source=source, permissions=permissions)
        await self._add_item(api_key)
        return api_key

    async def get_api_key_count(self, user_id: str) -> int:
        table = await self.db.Table(TABLE_NAME)
        item_dict = await table.scan(
            IndexName="type_index",
            Select="COUNT",
            FilterExpression=Key("type").eq(APIKey.__name__) & Key("user_id").eq(user_id),
        )
        return item_dict["Count"]

    async def delete_api_key(self, token: APIKey | str) -> None:
        await self._delete_item(token)

    async def list_api_keys(self, user_id: str) -> list[APIKey]:
        keys = await self._get_items_from_secondary_index("user_id", user_id, APIKey)
        keys.sort(key=lambda x: x.created_at, reverse=True)
        return keys

    async def update_user(self, user_id: str, updates: dict[str, Any]) -> User:
        if not updates:
            raise ValueError("No updates provided")

        user = await self.get_user(user_id, throw_if_missing=True)

        user.update_timestamp()
        updates["updated_at"] = user.updated_at

        try:
            await self._update_item(user_id, User, updates)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ValidationException":
                raise ValueError(f"Invalid update: {str(e)}")
            raise

        return await self.get_user(user_id, throw_if_missing=True)

    async def set_moderator(self, user_id: str, is_mod: bool) -> User:
        user = await self.get_user(user_id, throw_if_missing=True)
        if user.permissions is None:
            user.permissions = set()
        if is_mod:
            user.permissions.add("is_mod")
        else:
            user.permissions.discard("is_mod")
        await self._update_item(user_id, User, {"permissions": list(user.permissions)})
        return user

    async def set_username(self, user_id: str, new_username: str) -> User:
        user = await self.get_user(user_id, throw_if_missing=True)
        user.set_username(new_username)
        await self._update_item(user_id, User, {"username": new_username, "updated_at": user.updated_at})

        # Update username in all listings
        listings_crud = ListingsCrud()
        async with listings_crud:
            await listings_crud.update_username_for_user_listings(user_id, new_username)

        return user

    async def is_username_taken(self, username: str) -> bool:
        logger.info("Checking if username %s is taken", username)
        existing_users = await self._get_items_from_secondary_index("username", username, User)
        logger.info("existing_users: %s", existing_users)
        return len(existing_users) > 0

    async def generate_unique_username(self, base: str) -> str:
        username = base
        while await self.is_username_taken(username):
            random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
            username = f"{base}{random_suffix}"
        return username

    async def set_content_manager(self, user_id: str, is_content_manager: bool) -> User:
        user = await self.get_user(user_id, throw_if_missing=True)
        if user.permissions is None:
            user.permissions = set()
        if is_content_manager:
            user.permissions.add("is_content_manager")
        else:
            user.permissions.discard("is_content_manager")

        await self._update_item(user_id, User, {"permissions": list(user.permissions)})
        return user


async def test_adhoc() -> None:
    async with UserCrud() as crud:
        await crud._create_user_from_email(email="ben@kscale.dev", password="examplepas$w0rd")
        await crud.get_user_from_github_token(token="gh_token_example", email="oauth_github@kscale.dev")
        await crud.get_user_from_google_token(email="oauth_google@kscale.dev")


if __name__ == "__main__":
    asyncio.run(test_adhoc())
