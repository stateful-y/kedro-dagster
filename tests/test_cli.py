import contextlib
import importlib
import json
import os
import re
import subprocess
import sys

import click
import pytest
from click.testing import CliRunner
from kedro.framework.cli.cli import info
from kedro.framework.startup import bootstrap_project

from kedro_dagster import utils
from kedro_dagster.cli import dagster_commands as cli_dagster
from kedro_dagster.cli import init as cli_init
from kedro_dagster.utils import DAGSTER_VERSION

if DAGSTER_VERSION >= (1, 10, 6):
    from kedro_dagster.cli import DgProxyCommand


def _extract_cmd_from_help(msg: str) -> list[str]:
    """Parse Click help text and extract the list of top-level commands."""
    match = re.search(r"(?<=Commands:)([\s\S]+)$", msg)
    if not match:
        return []
    cmd_txt = match.group(1)
    cmd_list_detailed = cmd_txt.split("\n")

    cmd_list: list[str] = []
    for cmd_detailed in cmd_list_detailed:
        cmd_match = re.search(r"\w+(?=  )", string=cmd_detailed)
        if cmd_match is not None:
            cmd_list.append(cmd_match.group(0))
    return cmd_list


def _assert_args_map(called_args: list[str]) -> dict[str, str]:
    return {
        called_args[i]: called_args[i + 1]
        for i in range(2, len(called_args))
        if str(called_args[i]).startswith("--")
        and i + 1 < len(called_args)
        and not str(called_args[i + 1]).startswith("--")
    }


class TestCliDiscovery:
    """Tests for CLI command discovery and plugin registration."""

    def test_dagster_commands_discovered(self, monkeypatch, kedro_project_no_dagster_config_base):
        """Discover 'dagster' plugin commands in the Kedro CLI entrypoint."""
        options = kedro_project_no_dagster_config_base
        project_path = options.project_path
        monkeypatch.chdir(project_path)
        runner = CliRunner()

        result = runner.invoke(cli_dagster, ["--help"])

        assert result.exit_code == 0
        cmds = set(_extract_cmd_from_help(result.output))
        assert {"init", "dev"}.issubset(cmds)
        assert "You have not updated your template yet" not in result.output

    def test_plugin_shows_in_info(self, monkeypatch, tmp_path):
        """The 'kedro_dagster' plugin appears in 'kedro info' output."""
        monkeypatch.chdir(tmp_path)
        runner = CliRunner()

        result = runner.invoke(info)

        assert result.exit_code == 0
        assert "kedro_dagster" in result.output


class TestCliInit:
    """Tests for the 'kedro dagster init' command."""

    @pytest.mark.parametrize("inside_subdirectory", (True, False))
    def test_creates_files(self, monkeypatch, kedro_project_no_dagster_config_base, inside_subdirectory):
        """CLI 'init' writes dagster.yml and package definitions.py in the project."""
        options = kedro_project_no_dagster_config_base
        project_path = options.project_path
        bootstrap_project(project_path)

        cwd = project_path / "src" if inside_subdirectory else project_path
        monkeypatch.chdir(cwd)

        cli_runner = CliRunner()
        result = cli_runner.invoke(cli_init)

        assert result.exit_code == 0

        dagster_yml = project_path / "conf" / options.env / "dagster.yml"
        assert dagster_yml.is_file()
        assert (
            "'conf/base/dagster.yml' successfully updated." in result.output
            or "A 'dagster.yml' already exists" in result.output
        )

        pkg_dirs = list((project_path / "src").glob("*/definitions.py"))
        assert pkg_dirs, "definitions.py not created under src/<package>/"
        assert (
            "definitions.py' successfully updated." in result.output
            or "A 'definitions.py' already exists" in result.output
        )

        dg_toml = project_path / "dg.toml"
        if DAGSTER_VERSION >= (1, 10, 6):
            assert dg_toml.is_file()
            assert ("'dg.toml' successfully updated." in result.output) or (
                "A 'dg.toml' already exists" in result.output
            )
        else:
            assert not dg_toml.exists()

    def test_existing_config_shows_warning(self, monkeypatch, kedro_project_no_dagster_config_base):
        """A second 'init' without --force warns about existing config files."""
        project_path = kedro_project_no_dagster_config_base.project_path
        monkeypatch.chdir(project_path)
        runner = CliRunner()

        first = runner.invoke(cli_init)
        assert first.exit_code == 0

        second = runner.invoke(cli_init)

        assert second.exit_code == 0
        assert "A 'dagster.yml' already exists" in second.output
        assert "A 'definitions.py' already exists" in second.output
        if DAGSTER_VERSION >= (1, 10, 6):
            assert "A 'dg.toml' already exists" in second.output

    def test_force_overwrites(self, monkeypatch, kedro_project_no_dagster_config_base):
        """'init --force' overwrites existing configuration files successfully."""
        project_path = kedro_project_no_dagster_config_base.project_path
        monkeypatch.chdir(project_path)
        runner = CliRunner()
        runner.invoke(cli_init)

        result = runner.invoke(cli_init, ["--force"])

        assert result.exit_code == 0
        assert "successfully updated" in result.output
        assert (kedro_project_no_dagster_config_base.project_path / "dg.toml").is_file()

    def test_wrong_env_prints_message(self, monkeypatch, kedro_project_no_dagster_config_base):
        """Invalid --env prints a helpful message and exits cleanly."""
        project_path = kedro_project_no_dagster_config_base.project_path
        monkeypatch.chdir(project_path)
        runner = CliRunner()

        result = runner.invoke(cli_init, ["--env", "debug"])

        assert result.exit_code == 0
        assert "No env 'debug' found" in result.output

    def test_silent_suppresses_success_logs(self, monkeypatch, kedro_project_no_dagster_config_base):
        """'--silent' suppresses success logs while still performing updates."""
        project_path = kedro_project_no_dagster_config_base.project_path
        monkeypatch.chdir(project_path)
        runner = CliRunner()

        result = runner.invoke(cli_init, ["--force", "--silent"])

        assert result.exit_code == 0
        assert "successfully updated" not in result.output


class TestCliDev:
    """Tests for the 'kedro dagster dev' command."""

    @pytest.mark.parametrize("inside_subdirectory", (True, False))
    def test_invokes_dg(self, monkeypatch, mocker, kedro_project_no_dagster_config_base, inside_subdirectory):
        """'kedro dagster dev' proxies to 'dg dev' with pass-through args."""
        project_path = kedro_project_no_dagster_config_base.project_path
        cwd = project_path / "src" if inside_subdirectory else project_path
        monkeypatch.chdir(cwd)

        runner = CliRunner()
        sp_call = mocker.patch("kedro_dagster.cli.subprocess.call")

        result = runner.invoke(cli_dagster, ["dev"])

        assert result.exit_code == 0
        called_args = sp_call.call_args[0][0]
        if DAGSTER_VERSION >= (1, 10, 6):
            assert called_args[:2] == ["dg", "dev"]
        else:
            assert called_args[:2] == ["dagster", "dev"]

    def test_overrides_forwarded(self, monkeypatch, mocker, kedro_project_no_dagster_config_base):
        """Explicit flags are forwarded to 'dg dev' unmodified."""
        project_path = kedro_project_no_dagster_config_base.project_path
        monkeypatch.chdir(project_path)
        bootstrap_project(project_path)

        runner = CliRunner()
        sp_call = mocker.patch("kedro_dagster.cli.subprocess.call")
        if DAGSTER_VERSION >= (1, 10, 6):
            result = runner.invoke(
                cli_dagster,
                [
                    "dev",
                    "--",
                    "--log-level",
                    "debug",
                    "--log-format",
                    "json",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "4000",
                    "--live-data-poll-rate",
                    "1500",
                ],
            )
        else:
            result = runner.invoke(
                cli_dagster,
                [
                    "dev",
                    "--log-level",
                    "debug",
                    "--log-format",
                    "json",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "4000",
                    "--live-data-poll-rate",
                    "1500",
                ],
            )

        assert result.exit_code == 0
        called_args = sp_call.call_args[0][0]
        assert called_args[:2] == ["dg", "dev"]
        args_map = _assert_args_map(called_args)
        assert args_map["--log-level"] == "debug"
        assert args_map["--log-format"] == "json"
        assert args_map["--host"] == "0.0.0.0"
        assert args_map["--port"] == "4000"
        assert args_map["--live-data-poll-rate"] == "1500"

    def test_help_includes_underlying_options(self, monkeypatch, kedro_project_no_dagster_config_base):
        """Help for 'kedro dagster dev' includes both wrapper and underlying dg options."""
        project_path = kedro_project_no_dagster_config_base.project_path
        monkeypatch.chdir(project_path)

        runner = CliRunner()

        result = runner.invoke(cli_dagster, ["dev", "--help"])

        assert result.exit_code == 0
        out = result.output
        assert "-e, --env" in out
        assert "--log-level" in out
        assert "--log-format" in out
        assert "--host" in out
        assert "--port" in out
        if DAGSTER_VERSION >= (1, 10, 6):
            assert "Start a local instance of Dagster" in out
            assert "Options from 'dg dev'" not in out

    def test_no_duplication_when_user_flags_provided(self, monkeypatch, mocker, kedro_project_no_dagster_config_base):
        """If user supplies flags, wrapper must not append defaults or duplicate them."""
        project_path = kedro_project_no_dagster_config_base.project_path
        monkeypatch.chdir(project_path)

        runner = CliRunner()
        sp_call = mocker.patch("kedro_dagster.cli.subprocess.call")

        result = runner.invoke(
            cli_dagster,
            [
                "dev",
                "--log-level",
                "debug",
                "--log-format",
                "json",
            ],
        )

        assert result.exit_code == 0
        called_args = sp_call.call_args[0][0]
        args_map = _assert_args_map(called_args)
        assert args_map.get("--log-level") == "debug"
        assert args_map.get("--log-format") == "json"


class TestDgProxyCommand:
    """Tests for the DgProxyCommand class."""

    def test_help_handles_missing_underlying_command(self, monkeypatch):
        """Help rendering does not fail when the proxy has no underlying click.Command."""
        if DAGSTER_VERSION < (1, 10, 6):
            pytest.skip("DgProxyCommand is only defined for Dagster >= 1.10.6")

        proxy_cmd = DgProxyCommand(
            name="dummy",
            params=[
                click.Option(["--env", "-e"], required=False, default="local", help="The Kedro environment to use"),
                click.Argument(["args"], nargs=-1, type=click.UNPROCESSED),
            ],
            callback=lambda env, args: None,
            help="Dummy proxy",
            context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
            underlying_cmd=None,
        )

        grp = click.Group()
        grp.add_command(proxy_cmd)
        runner = CliRunner()

        result = runner.invoke(grp, ["dummy", "--help"])

        assert result.exit_code == 0
        assert "-e, --env" in result.output

    def test_help_skips_non_parameter_entries(self, monkeypatch):
        """format_options silently skips objects in underlying_cmd.params that are not click.Parameter."""
        if DAGSTER_VERSION < (1, 10, 6):
            pytest.skip("DgProxyCommand only defined for Dagster >= 1.10.6")

        class DummyUnderlying(click.Command):
            def __init__(self) -> None:
                super().__init__(name="dummy_underlying")
                self.params = [
                    click.Option(["--alpha"], help="Alpha option"),
                    object(),
                ]

        underlying = DummyUnderlying()

        proxy_cmd = DgProxyCommand(
            name="dummy2",
            params=[
                click.Option(["--env", "-e"], required=False, default="local", help="The Kedro environment to use"),
                click.Argument(["args"], nargs=-1, type=click.UNPROCESSED),
            ],
            callback=lambda env, args: None,
            help="Dummy proxy 2",
            context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
            underlying_cmd=underlying,
        )

        grp = click.Group()
        grp.add_command(proxy_cmd)
        runner = CliRunner()

        result = runner.invoke(grp, ["dummy2", "--help"])

        assert result.exit_code == 0
        assert "-e, --env" in result.output
        assert "--alpha" in result.output
        assert "Traceback" not in result.output


class TestCliVersionGating:
    """Tests for CLI behavior across different Dagster versions."""

    def test_old_branch_with_reload(self, monkeypatch):
        """Monkeypatch DAGSTER_VERSION to older and reload CLI to cover the else branch."""
        original_version = utils.DAGSTER_VERSION
        try:
            monkeypatch.setattr(utils, "DAGSTER_VERSION", (1, 10, 5), raising=False)
            sys.modules.pop("kedro_dagster.cli", None)
            cli_mod = importlib.import_module("kedro_dagster.cli")
            importlib.reload(cli_mod)

            runner = CliRunner()

            result = runner.invoke(cli_mod.dagster_commands, ["dev", "--help"])

            assert result.exit_code == 0
            out = result.output
            assert "-e, --env" in out
            assert "--log-level" in out
            assert "--log-format" in out
            assert "--host" in out
            assert "--port" in out
            assert "--live-data-poll-rate" in out
        finally:
            with contextlib.suppress(Exception):
                utils.DAGSTER_VERSION = original_version
            sys.modules.pop("kedro_dagster.cli", None)
            cli_mod = importlib.import_module("kedro_dagster.cli")
            importlib.reload(cli_mod)

    def test_old_branch_invokes_dagster(self, monkeypatch, mocker, kedro_project_no_dagster_config_base):
        """Under old CLI branch, 'kedro dagster dev' calls 'dagster dev' with provided flags."""
        project_path = kedro_project_no_dagster_config_base.project_path
        monkeypatch.chdir(project_path)

        original_version = utils.DAGSTER_VERSION
        try:
            monkeypatch.setattr(utils, "DAGSTER_VERSION", (1, 10, 5), raising=False)
            importlib.import_module("kedro_dagster.cli")
            sys.modules.pop("kedro_dagster.cli", None)
            cli_mod = importlib.import_module("kedro_dagster.cli")
            importlib.reload(cli_mod)

            sp_call = mocker.patch("kedro_dagster.cli.subprocess.call")
            runner = CliRunner()

            result = runner.invoke(
                cli_mod.dagster_commands,
                [
                    "dev",
                    "-e",
                    kedro_project_no_dagster_config_base.env,
                    "--log-level",
                    "info",
                    "--log-format",
                    "json",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "1234",
                    "--live-data-poll-rate",
                    "10",
                ],
            )

            assert result.exit_code == 0
            called_args = sp_call.call_args[0][0]
            assert called_args[:2] == ["dagster", "dev"]
            assert "--python-file" in called_args
            py_idx = called_args.index("--python-file") + 1
            defs_path = called_args[py_idx]
            assert str(defs_path).startswith(str(project_path / "src"))
            assert str(defs_path).endswith("definitions.py")

            args_map = _assert_args_map(called_args)
            assert args_map["--log-level"] == "info"
            assert args_map["--log-format"] == "json"
            assert args_map["--host"] == "0.0.0.0"
            assert args_map["--port"] == "1234"
            assert args_map["--live-data-poll-rate"] == "10"

            kwargs = sp_call.call_args[1]
            assert kwargs["cwd"] == str(project_path)
            assert kwargs["env"]["KEDRO_ENV"] == kedro_project_no_dagster_config_base.env
        finally:
            utils.DAGSTER_VERSION = original_version
            sys.modules.pop("kedro_dagster.cli", None)
            cli_mod = importlib.import_module("kedro_dagster.cli")
            importlib.reload(cli_mod)

    @pytest.mark.parametrize("inside_subdirectory", (True, False))
    def test_old_branch_from_subdir(
        self, monkeypatch, mocker, kedro_project_no_dagster_config_base, inside_subdirectory
    ):
        """Old branch works regardless of being run from project root or src/ subdir."""
        project_path = kedro_project_no_dagster_config_base.project_path
        cwd = project_path / "src" if inside_subdirectory else project_path
        monkeypatch.chdir(cwd)

        original_version = utils.DAGSTER_VERSION
        try:
            monkeypatch.setattr(utils, "DAGSTER_VERSION", (1, 10, 5), raising=False)
            sys.modules.pop("kedro_dagster.cli", None)
            cli_mod = importlib.import_module("kedro_dagster.cli")
            importlib.reload(cli_mod)

            sp_call = mocker.patch("kedro_dagster.cli.subprocess.call")
            runner = CliRunner()

            result = runner.invoke(
                cli_mod.dagster_commands,
                [
                    "dev",
                    "-e",
                    kedro_project_no_dagster_config_base.env,
                    "--log-level",
                    "debug",
                    "--log-format",
                    "color",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "5678",
                    "--live-data-poll-rate",
                    "5",
                ],
            )

            assert result.exit_code == 0
            called_args = sp_call.call_args[0][0]
            assert called_args[:2] == ["dagster", "dev"]
            kwargs = sp_call.call_args[1]
            assert kwargs["cwd"] == str(project_path)
            assert kwargs["env"]["KEDRO_ENV"] == kedro_project_no_dagster_config_base.env
        finally:
            utils.DAGSTER_VERSION = original_version
            sys.modules.pop("kedro_dagster.cli", None)
            cli_mod = importlib.import_module("kedro_dagster.cli")
            importlib.reload(cli_mod)


class TestCliListDefs:
    """Tests for the 'kedro dagster list defs' command."""

    @pytest.mark.skipif(utils.DAGSTER_VERSION < (1, 11, 0), reason="dg list defs commands require dagster>=1.11.0")
    def test_mocked_proxies_to_dg_list_defs(self, kedro_project_spaceflights_quickstart_base, monkeypatch, mocker):
        """list defs command proxies to dg list defs with correct arguments."""
        project_path = kedro_project_spaceflights_quickstart_base.project_path
        monkeypatch.chdir(project_path)
        runner = CliRunner()
        init_result = runner.invoke(cli_init, ["-e", kedro_project_spaceflights_quickstart_base.env])
        assert init_result.exit_code == 0

        sp_call = mocker.patch("kedro_dagster.cli.subprocess.call")

        result = runner.invoke(
            cli_dagster,
            ["list", "defs", "-e", kedro_project_spaceflights_quickstart_base.env],
        )

        assert result.exit_code == 0
        called_args = sp_call.call_args[0][0]
        assert called_args[:3] == ["dg", "list", "defs"]
        kwargs = sp_call.call_args[1]
        assert kwargs["cwd"] == str(project_path)
        assert kwargs["env"]["KEDRO_ENV"] == kedro_project_spaceflights_quickstart_base.env

    @pytest.mark.skipif(utils.DAGSTER_VERSION < (1, 11, 0), reason="dg list defs commands require dagster>=1.11.0")
    @pytest.mark.skipif(
        utils.KEDRO_VERSION < (1, 0, 0) and utils.is_mlflow_enabled(),
        reason="MLflow emits warnings that break dg list defs",
    )
    def test_real_subprocess_returns_definitions(self, kedro_project_exec_filebacked_base, monkeypatch):
        """Integration: list defs returns expected definitions from a scenario."""
        project_path = kedro_project_exec_filebacked_base.project_path
        monkeypatch.chdir(project_path)
        runner = CliRunner()
        init_result = runner.invoke(cli_init, ["-e", kedro_project_exec_filebacked_base.env])
        assert init_result.exit_code == 0
        env = kedro_project_exec_filebacked_base.env

        result = subprocess.run(
            ["dg", "list", "defs", "--json"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            env={**os.environ, "KEDRO_ENV": env},
            check=False,
        )

        assert result.returncode == 0, f"dg list defs failed: {result.stderr}"
        output = json.loads(result.stdout)
        assert isinstance(output, dict), f"Expected dict output, got {type(output)}"
        jobs = output.get("jobs", [])
        job_names = [job["name"] for job in jobs]
        assert len(job_names) >= 1, f"Expected at least 1 job in {job_names}"
        assets = output.get("assets", [])
        asset_keys = [asset.get("asset_key") or asset["key"] for asset in assets]
        assert len(asset_keys) >= 1, f"Expected at least 1 asset in {asset_keys}"

    @pytest.mark.skipif(utils.DAGSTER_VERSION < (1, 11, 0), reason="dg list defs commands require dagster>=1.11.0")
    @pytest.mark.skipif(
        utils.KEDRO_VERSION < (1, 0, 0) and utils.is_mlflow_enabled(),
        reason="MLflow emits warnings that break dg list defs",
    )
    def test_real_subprocess_with_local_env(self, kedro_project_exec_filebacked_local, monkeypatch):
        """Integration: list defs works with 'local' environment."""
        project_path = kedro_project_exec_filebacked_local.project_path
        monkeypatch.chdir(project_path)
        runner = CliRunner()
        init_result = runner.invoke(cli_init, ["-e", kedro_project_exec_filebacked_local.env])
        assert init_result.exit_code == 0
        env = kedro_project_exec_filebacked_local.env

        result = subprocess.run(
            ["dg", "list", "defs", "--json"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            env={**os.environ, "KEDRO_ENV": env},
            check=False,
        )

        assert result.returncode == 0, f"dg list defs failed: {result.stderr}"
        output = json.loads(result.stdout)
        assert isinstance(output, dict), f"Expected dict output, got {type(output)}"
        jobs = output.get("jobs", [])
        job_names = [job["name"] for job in jobs]
        assert len(job_names) >= 1, f"Expected at least 1 job, got {job_names}"
        assets = output.get("assets", [])
        asset_keys = [asset.get("asset_key") or asset["key"] for asset in assets]
        assert len(asset_keys) >= 1, f"Expected at least 1 asset, got {asset_keys}"
