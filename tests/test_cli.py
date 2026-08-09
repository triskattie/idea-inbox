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


@pytest.mark.parametrize(
    ("args", "expected_message"),
    [
        (["dev"], "development API startup is not implemented yet"),
        (
            ["serve", "--host", "127.0.0.1", "--port", "8080"],
            "API server startup is not implemented yet",
        ),
    ],
)
def test_planned_commands_dispatch_to_actionable_startup_failures(
    args: list[str], expected_message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code, stdout, stderr = invoke_cli(args, capsys)

    assert exit_code == 1
    assert stdout == ""
    assert expected_message in stderr
    assert "secrets" not in stderr.lower()


def test_migrate_applies_sqlite_migrations_to_requested_database(
    tmp_path, capsys: pytest.CaptureFixture[str]
) -> None:
    database_path = tmp_path / "idea-inbox.sqlite3"

    exit_code, stdout, stderr = invoke_cli(["migrate", "--database", str(database_path)], capsys)

    assert exit_code == 0
    assert stderr == ""
    assert stdout == f"Applied SQLite migrations to {database_path}\n"
    assert database_path.exists()
