"""Command-line entry point for Idea Inbox."""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from idea_inbox.api.server import run_api_server
from idea_inbox.config import ConfigError, load_config
from idea_inbox.storage.sqlite import SQLiteMigrationError, SQLiteStorageBackend

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080


def _port(value: str) -> int:
    try:
        port = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("port must be an integer") from exc

    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 1 and 65535")
    return port


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idea-inbox",
        description="Run and manage the Idea Inbox local service.",
    )
    subcommands = parser.add_subparsers(dest="command", metavar="<command>")

    dev = subcommands.add_parser(
        "dev",
        help="start the local development API with SQLite and mock/local providers",
    )
    dev.add_argument("--host", default=DEFAULT_HOST, help=f"bind host (default: {DEFAULT_HOST})")
    dev.add_argument(
        "--port",
        default=DEFAULT_PORT,
        type=_port,
        help=f"bind port (default: {DEFAULT_PORT})",
    )
    dev.add_argument(
        "--database",
        help="SQLite database path for the development API (default: configured path)",
    )
    dev.set_defaults(handler=_run_dev)

    migrate = subcommands.add_parser(
        "migrate",
        help="apply deterministic storage migrations for the configured backend",
    )
    migrate.add_argument(
        "--database",
        help="SQLite database path to migrate (default: configured IDEA_INBOX database path)",
    )
    migrate.set_defaults(handler=_run_migrate)

    serve = subcommands.add_parser(
        "serve",
        help="start the configured API process",
    )
    serve.add_argument("--host", default=DEFAULT_HOST, help=f"bind host (default: {DEFAULT_HOST})")
    serve.add_argument(
        "--port",
        default=DEFAULT_PORT,
        type=_port,
        help=f"bind port (default: {DEFAULT_PORT})",
    )
    serve.add_argument(
        "--database",
        help="SQLite database path for the API (default: configured path)",
    )
    serve.set_defaults(handler=_run_serve)

    return parser


def _run_dev(args: argparse.Namespace) -> int:
    return _run_api_surface(args, label="development API")


def _run_api_surface(args: argparse.Namespace, *, label: str) -> int:
    try:
        database_path = _database_path_for_args(args)
        return run_api_server(args.host, args.port, database_path)
    except ConfigError as exc:
        print(f"idea-inbox: invalid configuration: {exc}", file=sys.stderr)
    except (OSError, SQLiteMigrationError) as exc:
        print(f"idea-inbox: failed to start {label}: {exc}", file=sys.stderr)
    return 1


def _database_path_for_args(args: argparse.Namespace) -> Path:
    if args.database:
        return Path(args.database)
    return load_config().database_path


def _run_migrate(args: argparse.Namespace) -> int:
    try:
        config = load_config()
    except ConfigError as exc:
        print(f"idea-inbox: invalid configuration: {exc}", file=sys.stderr)
        return 1

    database_path = args.database or config.database_path
    storage = SQLiteStorageBackend(database_path)
    try:
        storage.migrate()
    except SQLiteMigrationError as exc:
        print(f"idea-inbox: failed to apply SQLite migrations: {exc}", file=sys.stderr)
        return 1
    finally:
        storage.close()
    print(f"Applied SQLite migrations to {database_path}")
    return 0


def _run_serve(args: argparse.Namespace) -> int:
    return _run_api_surface(args, label="API server")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    normalized_argv = list(sys.argv[1:] if argv is None else argv)
    if not normalized_argv:
        parser.print_help()
        return 0

    args = parser.parse_args(normalized_argv)
    return args.handler(args)
