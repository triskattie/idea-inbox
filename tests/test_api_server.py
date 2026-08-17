import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from idea_inbox.api.server import create_api_server


def test_api_server_exposes_manual_capture_route(tmp_path) -> None:
    database_path = tmp_path / "ideas.sqlite3"

    with create_api_server("127.0.0.1", 0, database_path) as server:
        worker = Thread(target=server.handle_request)
        worker.start()
        host, port = server.server_address
        request = Request(
            f"http://{host}:{port}/v1/ideas",
            data=json.dumps({"text": "Capture this idea from the served API."}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        response = urlopen(request, timeout=5)
        worker.join(timeout=5)

    payload = json.loads(response.read().decode("utf-8"))

    assert response.status == 201
    assert not worker.is_alive()
    assert payload["item"]["text"] == "Capture this idea from the served API."
    assert payload["item"]["source"] == "manual"


def test_api_server_starts_with_query_disabled_and_returns_capability_error(tmp_path) -> None:
    database_path = tmp_path / "ideas.sqlite3"

    status = 0
    payload: dict = {}
    with create_api_server("127.0.0.1", 0, database_path) as server:
        worker = Thread(target=server.handle_request)
        worker.start()
        host, port = server.server_address
        request = Request(
            f"http://{host}:{port}/v1/query",
            data=json.dumps({"query": "local AI"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urlopen(request, timeout=5)
        except HTTPError as exc:
            status = exc.code
            payload = json.loads(exc.read().decode("utf-8"))
        worker.join(timeout=5)

    assert status == 503
    assert not worker.is_alive()
    assert payload["error"]["code"] == "CAPABILITY_DISABLED"
    assert payload["error"]["details"]["capability"] == "query-ai"
