from __future__ import annotations

import asyncio
import logging

from immich_dlna.config import Settings
from immich_dlna.dlna.model import (
    ALBUMS_CONTAINER,
    ALBUMS_ID,
    IMAGE_CLASS,
    ROOT_CONTAINER,
    ROOT_ID,
    TIMELINE_CONTAINER,
    TIMELINE_ID,
    VIDEO_CLASS,
    BrowseEntry,
    Container,
    MediaItem,
    album_object_id,
    asset_object_id,
    parse_album_id,
    parse_asset_id,
)
from immich_dlna.immich import ImmichAsset, ImmichClient, ImmichError


class ContentCatalog:
    def __init__(self, settings: Settings, immich_client: ImmichClient) -> None:
        self.settings = settings
        self.immich_client = immich_client
        self.logger = logging.getLogger("immich_dlna.catalog")
        self._asset_parent_cache: dict[str, str] = {}

    async def browse(
        self,
        object_id: str,
        browse_flag: str,
        starting_index: int,
        requested_count: int,
        sort_criteria: str = "",
    ) -> tuple[list[BrowseEntry], int]:
        try:
            if browse_flag == "BrowseDirectChildren" and object_id in {TIMELINE_ID, "1"}:
                return await self._browse_timeline_paged(starting_index, requested_count)

            if browse_flag == "BrowseMetadata":
                entry = await self._browse_metadata(object_id)
                all_entries = [entry] if entry is not None else []
            else:
                all_entries = await self._browse_children(object_id, sort_criteria=sort_criteria)
        except ImmichError as error:
            if (
                object_id in {ROOT_ID, TIMELINE_ID, ALBUMS_ID, "1", "2"}
                or object_id.startswith("album:")
            ):
                self.logger.error("Immich browse fallback object_id=%s error=%s", object_id, error)
                all_entries = self._fallback_for(object_id, browse_flag)
            else:
                raise

        total_matches = len(all_entries)
        paged_entries = all_entries[starting_index : starting_index + requested_count]
        return paged_entries, total_matches

    async def _browse_metadata(self, object_id: str) -> BrowseEntry | None:
        if object_id == "1":
            object_id = TIMELINE_ID
        if object_id == "2":
            object_id = ALBUMS_ID
        if object_id == ROOT_ID:
            return ROOT_CONTAINER
        if object_id == TIMELINE_ID:
            return Container(
                object_id=TIMELINE_CONTAINER.object_id,
                parent_id=TIMELINE_CONTAINER.parent_id,
                title=TIMELINE_CONTAINER.title,
                child_count=len(await self.immich_client.list_timeline_asset_refs()),
            )
        if object_id == ALBUMS_ID:
            return Container(
                object_id=ALBUMS_CONTAINER.object_id,
                parent_id=ALBUMS_CONTAINER.parent_id,
                title=ALBUMS_CONTAINER.title,
                child_count=len(await self.immich_client.list_albums()),
            )

        album_id = parse_album_id(object_id)
        if album_id is not None:
            albums = await self.immich_client.list_albums()
            for album in albums:
                if album.album_id == album_id:
                    return Container(
                        object_id=album_object_id(album.album_id),
                        parent_id=ALBUMS_ID,
                        title=album.name,
                        child_count=album.asset_count,
                    )
            return None

        asset_id = parse_asset_id(object_id)
        if asset_id is not None:
            asset = await self.immich_client.get_asset_info(asset_id)
            parent_id = self._asset_parent_cache.get(asset.asset_id, TIMELINE_ID)
            return self._to_media_item(asset, parent_id)

        return None

    async def _browse_children(self, object_id: str, sort_criteria: str = "") -> list[BrowseEntry]:
        if object_id == "1":
            object_id = TIMELINE_ID
        if object_id == "2":
            object_id = ALBUMS_ID
        if object_id == ROOT_ID:
            return [TIMELINE_CONTAINER, ALBUMS_CONTAINER]

        if object_id == TIMELINE_ID:
            return []

        if object_id == ALBUMS_ID:
            albums = await self.immich_client.list_albums()
            sorted_albums = sorted(albums, key=lambda album: album.created_at, reverse=True)
            return [
                Container(
                    object_id=album_object_id(album.album_id),
                    parent_id=ALBUMS_ID,
                    title=album.name,
                    child_count=album.asset_count,
                )
                for album in sorted_albums
            ]

        album_id = parse_album_id(object_id)
        if album_id is not None:
            assets = await self.immich_client.get_album_assets(album_id, sort_criteria=sort_criteria)
            parent_id = album_object_id(album_id)
            return [self._to_media_item(asset, parent_id) for asset in assets]

        return []

    async def _browse_timeline_paged(
        self,
        starting_index: int,
        requested_count: int,
    ) -> tuple[list[BrowseEntry], int]:
        refs = await self.immich_client.list_timeline_asset_refs()
        total_matches = len(refs)
        if not refs:
            return [], 0
        paged_refs = refs[starting_index : starting_index + requested_count]
        infos = await asyncio.gather(
            *[
                self.immich_client.get_asset_info(asset_id, fallback_is_image=is_image)
                for asset_id, is_image in paged_refs
            ],
            return_exceptions=True,
        )
        entries: list[BrowseEntry] = []
        for info in infos:
            if isinstance(info, Exception):
                self.logger.warning("Skipping timeline asset due to metadata error: %s", info)
                continue
            entries.append(self._to_media_item(info, TIMELINE_ID))
        return entries, total_matches

    def _to_media_item(self, asset: ImmichAsset, parent_id: str) -> MediaItem:
        self._asset_parent_cache[asset.asset_id] = parent_id
        return MediaItem(
            object_id=asset_object_id(asset.asset_id),
            parent_id=parent_id,
            title=asset.title,
            upnp_class=VIDEO_CLASS if asset.is_video else IMAGE_CLASS,
            resource_url=f"{self.settings.base_url}/media/asset/{asset.asset_id}",
            thumbnail_url=f"{self.settings.base_url}/media/asset/{asset.asset_id}/thumbnail",
            mime_type=asset.original_mime_type or "application/octet-stream",
            is_video=asset.is_video,
        )

    @staticmethod
    def _fallback_for(object_id: str, browse_flag: str) -> list[BrowseEntry]:
        if browse_flag == "BrowseMetadata":
            if object_id in {TIMELINE_ID, "1"}:
                return [TIMELINE_CONTAINER]
            if object_id in {ALBUMS_ID, "2"}:
                return [ALBUMS_CONTAINER]
        if object_id == ROOT_ID:
            return [TIMELINE_CONTAINER, ALBUMS_CONTAINER]
        return []
