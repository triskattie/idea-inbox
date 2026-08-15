"""HTTP server entry points for the Idea Inbox WSGI API."""

from __future__ import annotations

from pathlib import Path
from wsgiref.simple_server import WSGIServer, make_server

from idea_inbox.api.app import create_app
from idea_inbox.storage.sqlite import SQLiteStorageBackend


def create_api_server(host: str, port: int, database_path: str | Path) -> WSGIServer:
    """Create a migrated WSGI server for the configured SQLite-backed API."""
    storage = SQLiteStorageBackend(database_path)
    try:
        storage.migrate()
    finally:
        storage.close()
    return make_server(host, port, create_app(database_path=database_path))


def run_api_server(host: str, port: int, database_path: str | Path) -> int:
    """Run the API server until interrupted by the process supervisor or operator."""
    with create_api_server(host, port, database_path) as server:
        print(f"Serving Idea Inbox API on http://{host}:{port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Stopped Idea Inbox API")
    return 0
