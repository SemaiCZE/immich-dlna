from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from xml.etree import ElementTree as ET

from immich_dlna.dlna.catalog import ContentCatalog
from immich_dlna.dlna.didl import render_entries
from immich_dlna.dlna.model import ALBUMS_ID, TIMELINE_ID, Container
from immich_dlna.immich import ImmichAlbum, ImmichError


class ContentCatalogMetadataTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.immich_client = SimpleNamespace(
            list_timeline_asset_refs=AsyncMock(return_value=[("asset-1", True), ("asset-2", False)]),
            list_albums=AsyncMock(
                return_value=[
                    ImmichAlbum("album-1", "Album 1", "2026-01-01", 3),
                    ImmichAlbum("album-2", "Album 2", "2026-01-02", 0),
                ]
            ),
        )
        self.catalog = ContentCatalog(
            SimpleNamespace(base_url="http://localhost:8200"),
            self.immich_client,
        )

    async def test_timeline_metadata_reports_asset_count(self) -> None:
        entries, total_matches = await self.catalog.browse(
            TIMELINE_ID,
            "BrowseMetadata",
            starting_index=0,
            requested_count=50,
        )

        self.assertEqual(total_matches, 1)
        self.assertIsInstance(entries[0], Container)
        self.assertEqual(entries[0].child_count, 2)
        self.assertEqual(ET.fromstring(render_entries(entries))[0].attrib["childCount"], "2")
        self.immich_client.list_timeline_asset_refs.assert_awaited_once()

    async def test_albums_metadata_reports_album_count(self) -> None:
        entries, total_matches = await self.catalog.browse(
            ALBUMS_ID,
            "BrowseMetadata",
            starting_index=0,
            requested_count=50,
        )

        self.assertEqual(total_matches, 1)
        self.assertIsInstance(entries[0], Container)
        self.assertEqual(entries[0].child_count, 2)
        self.assertEqual(ET.fromstring(render_entries(entries))[0].attrib["childCount"], "2")
        self.immich_client.list_albums.assert_awaited_once()

    async def test_metadata_falls_back_to_container_when_immich_fails(self) -> None:
        self.immich_client.list_timeline_asset_refs.side_effect = ImmichError("unavailable")

        entries, total_matches = await self.catalog.browse(
            TIMELINE_ID,
            "BrowseMetadata",
            starting_index=0,
            requested_count=50,
        )

        self.assertEqual(total_matches, 1)
        self.assertIsInstance(entries[0], Container)
        self.assertEqual(entries[0].child_count, 0)
