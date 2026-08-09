"""Command-line entry point for Idea Inbox."""

import argparse
import sys
from collections.abc import Sequence

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
    dev.set_defaults(handler=_run_dev)

    migrate = subcommands.add_parser(
        "migrate",
        help="apply deterministic storage migrations for the configured backend",
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
    serve.set_defaults(handler=_run_serve)

    return parser


def _run_dev(args: argparse.Namespace) -> int:
    print(
        "idea-inbox: development API startup is not implemented yet; "
        "the CLI parsed dev options successfully and will wire into the API/server module "
        f"when it exists (host={args.host}, port={args.port}).",
        file=sys.stderr,
    )
    return 1


def _run_migrate(_args: argparse.Namespace) -> int:
    print(
        "idea-inbox: database migrations are not implemented yet; "
        "the CLI parsed migrate successfully and will wire into the storage migration module "
        "when it exists.",
        file=sys.stderr,
    )
    return 1


def _run_serve(args: argparse.Namespace) -> int:
    print(
        "idea-inbox: API server startup is not implemented yet; "
        "the CLI parsed serve options successfully and will wire into the API/server module "
        f"when it exists (host={args.host}, port={args.port}).",
        file=sys.stderr,
    )
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    normalized_argv = list(sys.argv[1:] if argv is None else argv)
    if not normalized_argv:
        parser.print_help()
        return 0

    args = parser.parse_args(normalized_argv)
    return args.handler(args)
