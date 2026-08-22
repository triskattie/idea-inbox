import json
from pathlib import Path

from idea_inbox.connectors.discord import DiscordConnector
from idea_inbox.core.ports import Connector
from idea_inbox.core.services import ingest_connector_event
from idea_inbox.storage.sqlite import SQLiteStorageBackend

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "discord"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def make_storage(tmp_path) -> SQLiteStorageBackend:
    storage = SQLiteStorageBackend(tmp_path / "ideas.sqlite3")
    storage.migrate()
    return storage


def test_discord_connector_implements_connector_protocol() -> None:
    assert isinstance(DiscordConnector(), Connector)


def test_ingests_guild_message_create_fixture_into_raw_event_draft_and_idea(tmp_path) -> None:
    storage = make_storage(tmp_path)
    try:
        result = ingest_connector_event(
            storage, DiscordConnector(), load_fixture("message_create_guild.json")
        )

        assert result.duplicate is False
        assert result.raw_event.source == "discord"
        assert result.raw_event.provider_event_id == "1136811000000000001"
        assert result.raw_event.dedupe_key == "1136811000000000001"
        assert result.raw_event.actor_ref == "discord:user:1136814000000000004"
        assert result.raw_event.occurred_at == "2026-08-22T10:15:30.000000+00:00"
        assert (
            json.loads(result.raw_event.payload)["d"]["content"]
            == "Prototype Discord capture into Idea Inbox."
        )
        assert [draft.text for draft in result.drafts] == [
            "Prototype Discord capture into Idea Inbox."
        ]
        assert result.drafts[0].source_uri == (
            "discord://guilds/1136813000000000003/channels/1136812000000000002/"
            "messages/1136811000000000001"
        )
        assert result.ideas[0].source == "discord"
        assert result.ideas[0].source_ref == result.drafts[0].source_uri
    finally:
        storage.close()


def test_ingests_dm_message_create_fixture_without_guild_metadata(tmp_path) -> None:
    storage = make_storage(tmp_path)
    try:
        result = ingest_connector_event(
            storage, DiscordConnector(), load_fixture("message_create_dm.json")
        )

        assert result.raw_event.provider_event_id == "1136811000000000005"
        assert [draft.text for draft in result.drafts] == [
            "DM idea: capture private notes without guild metadata."
        ]
        assert result.drafts[0].source_uri == (
            "discord://channels/1136812000000000006/messages/1136811000000000005"
        )
        assert result.drafts[0].metadata["guild_id"] is None
    finally:
        storage.close()


def test_ingests_attachment_only_message_create_fixture_as_draft(tmp_path) -> None:
    storage = make_storage(tmp_path)
    try:
        result = ingest_connector_event(
            storage, DiscordConnector(), load_fixture("message_create_attachment_only.json")
        )

        assert [draft.text for draft in result.drafts] == [
            "Attachment: napkin-sketch.png (https://cdn.discordapp.com/attachments/"
            "1136812000000000009/1136815000000000012/napkin-sketch.png)"
        ]
        assert result.drafts[0].metadata["attachment_count"] == 1
        assert result.drafts[0].metadata["attachments"][0]["filename"] == "napkin-sketch.png"
    finally:
        storage.close()


def test_discord_provider_message_id_is_idempotent_for_raw_events_drafts_and_ideas(
    tmp_path,
) -> None:
    storage = make_storage(tmp_path)
    try:
        fixture = load_fixture("message_create_guild.json")

        first = ingest_connector_event(storage, DiscordConnector(), fixture)
        duplicate = ingest_connector_event(storage, DiscordConnector(), fixture)

        assert duplicate.duplicate is True
        assert duplicate.raw_event.id == first.raw_event.id
        assert [draft.id for draft in duplicate.drafts] == [draft.id for draft in first.drafts]
        assert [idea.id for idea in duplicate.ideas] == [idea.id for idea in first.ideas]
        assert storage.count_raw_events() == 1
        assert storage.list_idea_drafts(raw_event_id=first.raw_event.id) == list(first.drafts)
        assert [idea.id for idea in storage.list_ideas(raw_event_id=first.raw_event.id)] == [
            first.ideas[0].id
        ]
    finally:
        storage.close()
