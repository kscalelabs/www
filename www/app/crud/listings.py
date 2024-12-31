"""Defines CRUD interface for managing listings."""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Literal, Type, TypeVar, overload

from boto3.dynamodb.conditions import Attr

from www.app.crud.base import TABLE_NAME, BaseDbCrud, ItemNotFoundError
from www.app.model import Listing, ListingTag, ListingVote, User

T = TypeVar("T")

logger = logging.getLogger(__name__)


class SortOption(str, Enum):
    NEWEST = "newest"
    MOST_VIEWED = "most_viewed"
    MOST_UPVOTED = "most_upvoted"


class ListingsCrud(BaseDbCrud):
    PAGE_SIZE = 20

    @classmethod
    def get_gsis(cls) -> set[str]:
        return super().get_gsis().union({"listing_id", "name"})

    @overload
    async def get_listing(self, listing_id: str, throw_if_missing: Literal[True]) -> Listing: ...

    @overload
    async def get_listing(self, listing_id: str, throw_if_missing: bool = False) -> Listing | None: ...

    async def get_listing(self, listing_id: str, throw_if_missing: bool = False) -> Listing | None:
        return await self._get_item(listing_id, Listing, throw_if_missing=throw_if_missing)

    async def get_listings(
        self,
        page: int,
        search_query: str | None = None,
        sort_by: SortOption = SortOption.NEWEST,
    ) -> tuple[list[Listing], bool]:
        sort_key = self._get_sort_key(sort_by)
        try:
            listings, has_next = await self._list(Listing, page, sort_key, search_query)
            logger.info("Retrieved %s listings", len(listings))
            return listings, has_next
        except Exception as e:
            logger.exception("Error in get_listings: %s", e)
            raise

    def _get_sort_key(self, sort_by: SortOption) -> Callable[[Listing], Any]:
        match sort_by:
            case SortOption.NEWEST:
                return lambda x: (x.created_at or 0, x.name)
            case SortOption.MOST_VIEWED:
                return lambda x: (x.views, x.name)
            case SortOption.MOST_UPVOTED:
                return lambda x: (x.score, x.name)
            case _:
                return lambda x: (x.id, x.name)

    async def _list(
        self,
        item_class: Type[T],
        page: int,
        sort_key: Callable[[T], int] | None = None,
        search_query: str | None = None,
    ) -> tuple[list[T], bool]:
        table = await self.db.Table(TABLE_NAME)

        scan_params = {}
        if search_query:
            filter_expression = Attr("name").contains(search_query) | Attr("description").contains(search_query)
            scan_params["FilterExpression"] = filter_expression

        response = await table.scan(**scan_params)
        items = response["Items"]

        # Filter out items with missing required fields
        required_fields = {"updated_at", "name", "child_ids"}
        valid_items = [item for item in items if all(field in item for field in required_fields)]

        # Convert items to the correct model type
        try:
            typed_items = [item_class(**item) for item in valid_items]
        except Exception as e:
            logger.exception("Error creating %s objects: %s", item_class.__name__, e)
            raise

        if sort_key:
            sorted_items = sorted(typed_items, key=sort_key, reverse=True)
        else:
            sorted_items = typed_items

        # Paginate results
        start = (page - 1) * self.PAGE_SIZE
        end = start + self.PAGE_SIZE
        paginated_items = sorted_items[start:end]

        return paginated_items, len(sorted_items) > end

    async def get_user_listings(
        self,
        user_id: str,
        page: int,
        sort_by: SortOption = SortOption.NEWEST,
    ) -> tuple[list[Listing], bool]:
        sort_key = self._get_sort_key(sort_by)
        try:
            listings, has_next = await self._list_me(Listing, user_id, page, sort_key)
            logger.info("Retrieved %s listings for user %s", len(listings), user_id)
            return listings, has_next
        except Exception as e:
            logger.exception("Error in get_user_listings: %s", e)
            raise

    async def get_listings_by_ids(self, listing_ids: list[str]) -> list[Listing]:
        return await self._list_items(
            Listing,
            filter_expression=Attr("id").is_in(listing_ids),
        )

    async def dump_listings(self) -> list[Listing]:
        return await self._list_items(Listing)

    async def add_listing(self, listing: Listing) -> None:
        await self._add_item(listing)

    async def _delete_listing_tags(self, listing_id: str) -> None:
        listing_tags = await self._get_items_from_secondary_index("listing_id", listing_id, ListingTag)
        await asyncio.gather(*(self._delete_item(tag) for tag in listing_tags))

    async def delete_listing(self, listing: Listing) -> None:
        await asyncio.gather(
            self._delete_listing_artifacts(listing),
            self._delete_listing_tags(listing.id),
        )

        # Only delete the listing after all artifacts have been removed.
        await self._delete_item(listing)

    async def edit_listing(
        self,
        listing_id: str,
        name: str | None = None,
        child_ids: list[str] | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        onshape_url: str | None = None,
        slug: str | None = None,
    ) -> None:
        listing = await self.get_listing(listing_id)
        if listing is None:
            raise ItemNotFoundError("Listing not found")

        updates: dict[str, Any] = {}
        if name is not None:
            updates["name"] = name
        if child_ids is not None:
            updates["child_ids"] = child_ids
        if description is not None:
            updates["description"] = description
        if slug is not None:
            updates["slug"] = slug

        coroutines = []
        if tags is not None:
            coroutines.append(self.set_listing_tags(listing, tags))
        if onshape_url is not None:
            updates["onshape_url"] = onshape_url
        if updates:
            coroutines.append(self._update_item(listing_id, Listing, updates))

        if coroutines:
            await asyncio.gather(*coroutines)

    async def remove_onshape_url(self, listing_id: str) -> None:
        await self._update_item(listing_id, Listing, {"onshape_url": None})

    async def _add_tag_to_listing(self, listing_id: str, tag: str) -> None:
        await self._add_item(ListingTag.create(listing_id=listing_id, tag=tag), unique_fields=["listing_id", "name"])

    async def _remove_tag_from_listing(self, listing_id: str, tag: str) -> None:
        await self._delete_item(listing_id)

    async def set_listing_tags(self, listing: Listing, tags: list[str]) -> None:
        """For a given listing, determines which tags to add and which to remove.

        Args:
            listing: The listing to update.
            tags: The new tags to set.
        """
        tags_to_add = set(tags)
        tags_to_remove = set(await self.get_tags_for_listing(listing.id))
        tags_to_add.difference_update(tags_to_remove)
        tags_to_remove.difference_update(tags_to_add)
        await asyncio.gather(
            *(self._add_tag_to_listing(listing.id, tag) for tag in tags_to_add),
            *(self._remove_tag_from_listing(listing.id, tag) for tag in tags_to_remove),
        )

    async def get_tags_for_listing(self, listing_id: str) -> list[str]:
        listing_tags = await self._get_items_from_secondary_index("listing_id", listing_id, ListingTag)
        return [t.name for t in listing_tags]

    async def get_listing_ids_for_tag(self, tag: str) -> list[str]:
        listing_tags = await self._get_items_from_secondary_index("name", tag, ListingTag)
        return [t.listing_id for t in listing_tags]

    async def increment_view_count(self, listing: Listing) -> None:
        table = await self.db.Table(TABLE_NAME)
        await table.update_item(
            Key={"id": listing.id},
            UpdateExpression="ADD #views :inc",
            ExpressionAttributeNames={"#views": "views"},
            ExpressionAttributeValues={":inc": 1},
        )

    async def _update_vote(self, listing_id: str, upvote: bool) -> None:
        table = await self.db.Table(TABLE_NAME)
        await table.update_item(
            Key={"id": listing_id},
            UpdateExpression="ADD #vote_type :inc, score :score_inc",
            ExpressionAttributeNames={"#vote_type": "upvotes" if upvote else "downvotes"},
            ExpressionAttributeValues={":inc": 1, ":score_inc": 1 if upvote else -1},
        )

    async def _remove_vote(self, listing_id: str, was_upvote: bool) -> None:
        table = await self.db.Table(TABLE_NAME)
        await table.update_item(
            Key={"id": listing_id},
            UpdateExpression="ADD #vote_type :dec, score :score_dec",
            ExpressionAttributeNames={"#vote_type": "upvotes" if was_upvote else "downvotes"},
            ExpressionAttributeValues={":dec": -1, ":score_dec": -1 if was_upvote else 1},
            ConditionExpression=Attr(f"{'upvotes' if was_upvote else 'downvotes'}").gt(0),
        )

    async def get_user_vote(self, user_id: str, listing_id: str) -> ListingVote | None:
        votes = await self._get_items_from_secondary_index(
            secondary_index_name="user_id",
            secondary_index_value=user_id,
            item_class=ListingVote,
            additional_filter_expression=Attr("listing_id").eq(listing_id),
        )

        # If there are multiple votes, delete duplicates.
        if len(votes) > 1:
            await asyncio.gather(
                *(self._delete_item(vote) for vote in votes[1:]),
                *(self._remove_vote(vote.listing_id, vote.is_upvote) for vote in votes[1:]),
            )

        return votes[0] if votes else None

    async def handle_vote(self, user_id: str, listing_id: str, upvote: bool | None) -> None:
        """Handles a user vote.

        Args:
            user_id: The user ID.
            listing_id: The listing ID.
            upvote: True for upvote, False for downvote, None for remove vote.
        """
        listing = await self.get_listing(listing_id)
        if listing is None:
            raise ItemNotFoundError("Listing not found")

        existing_vote = await self.get_user_vote(user_id, listing.id)

        if existing_vote is None:
            if upvote is None:
                raise ValueError("Cannot remove a vote that does not exist")

            # If there is no existing vote, add a new one.
            new_vote = ListingVote.create(user_id=user_id, listing_id=listing_id, is_upvote=upvote)
            await asyncio.gather(
                self._add_item(new_vote),
                self._update_vote(listing_id, upvote),
            )

        elif upvote is None:
            # If the new vote is None, remove the existing vote.
            await asyncio.gather(
                self._remove_vote(listing_id, existing_vote.is_upvote),
                self._delete_item(existing_vote),
            )

        elif existing_vote.is_upvote == upvote:
            # If the new vote is the same as the old vote, do nothing.
            pass

        else:
            # If the new vote is different, toggle off the old vote and toggle on the new vote.
            await asyncio.gather(
                self._remove_vote(listing_id, existing_vote.is_upvote),
                self._update_vote(listing_id, upvote),
                self._update_item(existing_vote.id, ListingVote, {"is_upvote": upvote}),
            )

    async def get_user_votes(self, user_id: str, listing_ids: list[str]) -> list[ListingVote]:
        votes = await self._get_items_from_secondary_index("user_id", user_id, ListingVote)
        return [vote for vote in votes if vote.listing_id in listing_ids]

    async def get_upvoted_listings(self, user_id: str, page: int = 1) -> tuple[list[Listing], bool]:
        user_votes = await self._get_items_from_secondary_index(
            secondary_index_name="user_id", secondary_index_value=user_id, item_class=ListingVote
        )

        upvoted_listing_ids = [vote.listing_id for vote in user_votes if vote.is_upvote]

        if not upvoted_listing_ids:
            return [], False

        listings = await asyncio.gather(*(self.get_listing(listing_id) for listing_id in upvoted_listing_ids))
        listings = [listing for listing in listings if listing is not None]
        listings.sort(key=lambda x: x.created_at, reverse=True)

        start = (page - 1) * self.PAGE_SIZE
        end = start + self.PAGE_SIZE
        paginated_listings = listings[start:end]
        has_more = len(upvoted_listing_ids) > end
        return paginated_listings, has_more

    async def is_slug_taken(self, user_id: str, slug: str) -> bool:
        return await self.get_listing_by_username_and_slug(user_id, slug) is not None

    async def get_listing_by_username_and_slug(self, username: str, slug: str) -> Listing | None:
        # Get the user (listing creator) by username
        listing_creator = await self._get_unique_item_from_secondary_index("username", username, User)
        if listing_creator is None:
            return None

        # Get listings by the creator's user_id that match the slug
        listings = await self._get_items_from_secondary_index(
            "user_id", listing_creator.id, Listing, additional_filter_expression=Attr("slug").eq(slug)
        )
        return listings[0] if listings else None

    async def get_listings_with_usernames(self, listings: list[Listing]) -> list[tuple[Listing, str]]:
        """Get usernames for a list of listings by fetching their creators.

        Args:
            listings: List of listings to get usernames for

        Returns:
            List of tuples containing (listing, username)
        """
        # Get all unique user IDs from the listings
        user_ids = {listing.user_id for listing in listings}

        # Fetch all users in parallel
        users = await asyncio.gather(*(self._get_item(user_id, User) for user_id in user_ids))

        # Create mapping of user_id to username
        username_map = {user.id: user.username for user in users if user is not None}

        # Return listings paired with their creator's username
        return [(listing, username_map.get(listing.user_id, "unknown")) for listing in listings]

    async def update_username_for_user_listings(self, user_id: str, new_username: str) -> None:
        listings = await self._get_items_from_secondary_index("user_id", user_id, Listing)
        update_tasks = [self._update_item(listing.id, Listing, {"username": new_username}) for listing in listings]
        await asyncio.gather(*update_tasks)

    async def get_featured_listings(self) -> list[str]:
        featured = await self._get_by_known_id("featured_listings")
        if not featured:
            return []
        return list(featured["listing_ids"])

    async def set_featured_listings(self, listing_ids: list[str]) -> None:
        """Set the list of featured listing IDs."""
        table = await self.db.Table(TABLE_NAME)
        await table.put_item(
            Item={
                "id": "featured_listings",
                "type": "featured_listings",
                "listing_ids": listing_ids,
                "updated_at": int(time.time()),
            }
        )
