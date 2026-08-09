import importlib
import tomllib
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def project_metadata() -> dict[str, Any]:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as pyproject:
        return tomllib.load(pyproject)["project"]


def test_package_import_exposes_configured_version_metadata_baseline() -> None:
    idea_inbox = importlib.import_module("idea_inbox")

    assert idea_inbox.__version__ == project_metadata()["version"]


def test_console_script_metadata_points_to_existing_cli_callable_baseline() -> None:
    scripts = project_metadata()["scripts"]
    module_name, callable_name = scripts["idea-inbox"].split(":")

    cli_module = importlib.import_module(module_name)

    assert callable(getattr(cli_module, callable_name))
