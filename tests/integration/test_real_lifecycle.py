"""Isolated lifecycle coverage against the real ``uv`` executable."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.integration


@pytest.fixture
def isolated_tool_environment(tmp_path: Path) -> tuple[dict[str, str], Path, Path]:
    """Redirect every uv and uvs user-state location below ``tmp_path``."""
    if shutil.which("uv") is None:
        pytest.skip("real uv executable is not available")
    home = tmp_path / "home"
    appdata = tmp_path / "appdata"
    localappdata = tmp_path / "localappdata"
    config = tmp_path / "config"
    data = tmp_path / "data"
    cache = tmp_path / "cache"
    tools = tmp_path / "tools"
    bin_dir = tmp_path / "bin"
    python_bin_dir = tmp_path / "python-bin"
    python_dir = tmp_path / "python"
    python_cache_dir = tmp_path / "python-cache"
    credentials_dir = tmp_path / "credentials"
    temp_dir = tmp_path / "temp"
    for directory in (
        home,
        appdata,
        localappdata,
        config,
        data,
        cache,
        tools,
        bin_dir,
        python_bin_dir,
        python_dir,
        python_cache_dir,
        credentials_dir,
        temp_dir,
    ):
        directory.mkdir(parents=True)

    env = os.environ.copy()
    env.pop("UV_CONFIG_FILE", None)
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "APPDATA": str(appdata),
            "LOCALAPPDATA": str(localappdata),
            "XDG_CONFIG_HOME": str(config),
            "XDG_DATA_HOME": str(data),
            "XDG_CACHE_HOME": str(cache),
            "XDG_BIN_HOME": str(bin_dir),
            "UV_TOOL_DIR": str(tools),
            "UV_TOOL_BIN_DIR": str(bin_dir),
            "UV_CACHE_DIR": str(cache / "uv"),
            "UV_PYTHON_INSTALL_DIR": str(python_dir),
            "UV_PYTHON_BIN_DIR": str(python_bin_dir),
            "UV_PYTHON_CACHE_DIR": str(python_cache_dir),
            # setup-uv selects the matrix interpreter before pytest starts. Give
            # uv its exact path because the managed-Python directory below is
            # intentionally redirected to an empty sandbox.
            "UV_PYTHON": str(Path(sys.executable).resolve()),
            "UV_PYTHON_INSTALL_REGISTRY": "0",
            "UV_CREDENTIALS_DIR": str(credentials_dir),
            "UV_PYTHON_DOWNLOADS": "never",
            "UV_NO_CONFIG": "1",
            "UV_NO_PROGRESS": "1",
            "TMPDIR": str(temp_dir),
            "TEMP": str(temp_dir),
            "TMP": str(temp_dir),
            "PATH": os.pathsep.join((str(bin_dir), env.get("PATH", ""))),
            "PYTHONPATH": str(Path(__file__).parents[2] / "src"),
            "UVS_TEST_CWD": str(tmp_path),
        }
    )
    if os.name == "nt":
        env["HOMEDRIVE"] = home.drive
        env["HOMEPATH"] = str(home)[len(home.drive) :]
    return env, bin_dir, tmp_path


def run_checked(
    command: list[str | Path], env: dict[str, str], *, timeout: int = 180
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(part) for part in command],
        env=env,
        cwd=env["UVS_TEST_CWD"],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    assert result.returncode == 0, (
        f"command failed: {command!r}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return result


def write_tool(path: Path, message: str) -> None:
    path.write_text(
        f'''# /// script
# requires-python = ">=3.10"
# dependencies = ["packaging==24.2"]
# ///

def main():
    import packaging
    print("{message}:" + packaging.__version__)
''',
        encoding="utf8",
    )


def test_real_install_execute_dependency_update_list_show_uninstall(
    isolated_tool_environment: tuple[dict[str, str], Path, Path],
) -> None:
    env, bin_dir, sandbox = isolated_tool_environment
    script = sandbox / "source.py"
    command_name = "uvs-integration-tool"
    cli = [sys.executable, "-m", "uvs.cli", "--no-color"]
    write_tool(script, "first")

    for command, expected in (
        (["uv", "tool", "dir"], sandbox / "tools"),
        (["uv", "tool", "dir", "--bin"], bin_dir),
        (["uv", "cache", "dir"], sandbox / "cache" / "uv"),
        (["uv", "python", "dir"], sandbox / "python"),
        (["uv", "auth", "dir"], sandbox / "credentials"),
    ):
        resolved = Path(run_checked(command, env).stdout.strip()).resolve()
        assert resolved == expected.resolve()

    selected_python = Path(
        run_checked(["uv", "python", "find"], env).stdout.strip()
    ).resolve()
    assert selected_python == Path(sys.executable).resolve()

    run_checked([*cli, "install", "--name", command_name, script], env)

    executable = shutil.which(command_name, path=str(bin_dir))
    assert executable is not None
    first_run = run_checked([executable], env)
    assert first_run.stdout.startswith("first:")

    listed = run_checked([*cli, "list", "--format", "json"], env)
    list_payload = json.loads(listed.stdout)
    assert set(list_payload["tools"]) == {command_name}
    assert list_payload["tools"][command_name]["source_path"] == os.path.normcase(
        str(script.resolve())
    )
    first_hash = list_payload["tools"][command_name]["source_hash"]

    shown = run_checked([*cli, "show", "--format", "json", command_name], env)
    show_payload = json.loads(shown.stdout)
    assert show_payload["tools"][command_name]["version"] == "0.1.0"

    write_tool(script, "second")
    run_checked([*cli, "update", script], env)
    second_run = run_checked([executable], env)
    assert second_run.stdout.startswith("second:")
    updated = json.loads(
        run_checked([*cli, "show", "--format", "json", command_name], env).stdout
    )["tools"][command_name]
    assert updated["version"] == "0.1.1"
    assert updated["source_hash"] != first_hash

    uv_list = run_checked(["uv", "tool", "list"], env)
    assert command_name in uv_list.stdout

    run_checked(
        [*cli, "uninstall", "--force", "--no-backup", command_name], env
    )
    assert shutil.which(command_name, path=str(bin_dir)) is None
    assert command_name not in run_checked(["uv", "tool", "list"], env).stdout
    empty = run_checked([*cli, "list", "--format", "json"], env)
    assert json.loads(empty.stdout) == {"count": 0, "tools": {}}

    registries = list(sandbox.rglob("registry.json"))
    assert len(registries) == 1
    assert sandbox in registries[0].parents
