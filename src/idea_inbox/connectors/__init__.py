"""Optional connector adapters for external idea sources."""

from idea_inbox.connectors.discord import DiscordConnector
from idea_inbox.connectors.email import EmailConnector
from idea_inbox.connectors.manual import ManualConnector
from idea_inbox.connectors.telegram import TelegramConnector
from idea_inbox.connectors.webhook import GenericWebhookConnector

__all__ = [
    "DiscordConnector",
    "EmailConnector",
    "GenericWebhookConnector",
    "ManualConnector",
    "TelegramConnector",
]
