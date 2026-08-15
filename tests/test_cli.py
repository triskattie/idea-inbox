import pytest

from idea_inbox import cli


def invoke_cli(args: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    try:
        result = cli.main(args)
    except SystemExit as exc:
        result = exc.code
    captured = capsys.readouterr()
    return int(result or 0), captured.out, captured.err


def test_no_args_prints_top_level_help_for_smoke_command(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code, stdout, stderr = invoke_cli([], capsys)

    assert exit_code == 0
    assert stderr == ""
    assert "usage: idea-inbox" in stdout
    assert "dev" in stdout
    assert "migrate" in stdout
    assert "serve" in stdout


@pytest.mark.parametrize(
    "args",
    [["--help"], ["dev", "--help"], ["migrate", "--help"], ["serve", "--help"]],
)
def test_help_exits_zero(args: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    exit_code, stdout, stderr = invoke_cli(args, capsys)

    assert exit_code == 0
    assert stderr == ""
    assert "usage: idea-inbox" in stdout


@pytest.mark.parametrize(
    "args",
    [["unknown"], ["serve", "--port", "not-a-port"], ["dev", "--bogus"]],
)
def test_invalid_invocations_exit_two_with_usage_error(
    args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code, stdout, stderr = invoke_cli(args, capsys)

    assert exit_code == 2
    assert stdout == ""
    assert "usage: idea-inbox" in stderr
    assert "error:" in stderr


def test_serve_reports_configuration_errors_without_secrets(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("IDEA_INBOX_DATABASE_URL", "sqlite:///./one.sqlite3")
    monkeypatch.setenv("IDEA_INBOX_SQLITE_PATH", "./two.sqlite3")

    exit_code, stdout, stderr = invoke_cli(["serve"], capsys)

    assert exit_code == 1
    assert stdout == ""
    assert "invalid configuration" in stderr
    assert "secrets" not in stderr.lower()


def test_serve_starts_api_surface_for_manual_capture(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    database_path = tmp_path / "ideas.sqlite3"
    calls: list[tuple[str, int, object]] = []

    def fake_run_api_server(host: str, port: int, database_path: object) -> int:
        calls.append((host, port, database_path))
        return 0

    monkeypatch.setattr(cli, "run_api_server", fake_run_api_server)

    exit_code, stdout, stderr = invoke_cli(
        [
            "serve",
            "--host",
            "0.0.0.0",
            "--port",
            "9090",
            "--database",
            str(database_path),
        ],
        capsys,
    )

    assert exit_code == 0
    assert stdout == ""
    assert stderr == ""
    assert calls == [("0.0.0.0", 9090, database_path)]


def test_dev_starts_api_surface_with_configured_default_database(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    calls: list[tuple[str, int, object]] = []

    def fake_run_api_server(host: str, port: int, database_path: object) -> int:
        calls.append((host, port, database_path))
        return 0

    monkeypatch.setattr(cli, "run_api_server", fake_run_api_server)

    exit_code, stdout, stderr = invoke_cli(["dev"], capsys)

    assert exit_code == 0
    assert stdout == ""
    assert stderr == ""
    assert calls == [("127.0.0.1", 8080, tmp_path / "data" / "idea-inbox.sqlite3")]


def test_migrate_applies_sqlite_migrations_to_requested_database(
    tmp_path, capsys: pytest.CaptureFixture[str]
) -> None:
    database_path = tmp_path / "idea-inbox.sqlite3"

    exit_code, stdout, stderr = invoke_cli(["migrate", "--database", str(database_path)], capsys)

    assert exit_code == 0
    assert stderr == ""
    assert stdout == f"Applied SQLite migrations to {database_path}\n"
    assert database_path.exists()


def test_migrate_uses_configured_default_database_path(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code, stdout, stderr = invoke_cli(["migrate"], capsys)

    database_path = tmp_path / "data" / "idea-inbox.sqlite3"
    assert exit_code == 0
    assert stderr == ""
    assert stdout == f"Applied SQLite migrations to {database_path}\n"
    assert database_path.exists()
