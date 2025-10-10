"""Manage command tests using a real, minimal agentup.yml on disk.

We write a temp config file (the user-provided minimal YAML) and pass it via --config.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from agent.cli.commands.plugin import manage


MINIMAL_YAML = """
apiVersion: v1
name: test
description: AI Agent test Project.
version: 0.0.1
url: http://testing.localhost
provider_organization: AgentUp
provider_url: https://agentup.dev
icon_url: https://raw.githubusercontent.com/RedDotRocket/AgentUp/refs/heads/main/assets/icon.png
documentation_url: https://docs.agentup.dev

plugins:
  brave_search:
    capabilities:
      search_internet:
        required_scopes:
          - api:read
          - api:write

plugin_defaults:
  middleware:
    rate_limited:
      requests_per_minute: 60
      burst_size: 72
    cached:
      backend_type: memory
      default_ttl: 300
      max_size: 1000
    retryable:
      max_attempts: 3
      initial_delay: 1.0
      max_delay: 60.0
"""


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def cfg(tmp_path: Path) -> Path:
    path = tmp_path / "agentup.yml"
    path.write_text(MINIMAL_YAML, encoding="utf-8")
    return path


# -------------------- Tests --------------------

class TestManageWithFile:
    def test_add_scope_dry_run_only_shows_changes(self, runner: CliRunner, cfg: Path):
        before = cfg.read_text(encoding="utf-8")
        res = runner.invoke(
            manage,
            [
                "brave_search",
                "-a",
                "search_internet::search:web:query",
                "--dry-run",
                "--config",
                str(cfg),
            ],
        )
        assert res.exit_code == 0
        assert "DRY RUN" in res.output
        assert "search:web:query" in res.output
        after = cfg.read_text(encoding="utf-8")
        assert after == before  # unchanged

    def test_add_scope_persists(self, runner: CliRunner, cfg: Path):
        res = runner.invoke(
            manage,
            [
                "brave_search",
                "-a",
                "search_internet::search:web:query",
                "--config",
                str(cfg),
            ],
        )
        assert res.exit_code == 0
        data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        scopes = data["plugins"]["brave_search"]["capabilities"]["search_internet"]["required_scopes"]
        assert "search:web:query" in scopes

    def test_add_existing_scope_noop(self, runner: CliRunner, cfg: Path):
        # add once
        _ = runner.invoke(
            manage,
            ["brave_search", "-a", "search_internet::search:web:query", "--config", str(cfg)],
        )
        # add again
        res = runner.invoke(
            manage,
            ["brave_search", "-a", "search_internet::search:web:query", "--config", str(cfg)],
        )
        assert res.exit_code == 0
        assert "already exists" in res.output or "No changes" in res.output

    def test_remove_scope_persists(self, runner: CliRunner, cfg: Path):
        res = runner.invoke(
            manage,
            ["brave_search", "-r", "search_internet::api:write", "--config", str(cfg)],
        )
        assert res.exit_code == 0
        data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        scopes = data["plugins"]["brave_search"]["capabilities"]["search_internet"]["required_scopes"]
        assert "api:write" not in scopes

    def test_remove_missing_scope_warns(self, runner: CliRunner, cfg: Path):
        res = runner.invoke(
            manage,
            ["brave_search", "-r", "search_internet::no:such", "--config", str(cfg)],
        )
        assert res.exit_code == 0
        assert "not found" in res.output

    def test_invalid_format(self, runner: CliRunner, cfg: Path):
        res = runner.invoke(manage, ["brave_search", "-a", "badformat", "--config", str(cfg)])
        assert res.exit_code in (0, 1)
        assert "Invalid scope format" in res.output

    def test_unknown_plugin_errors(self, runner: CliRunner, cfg: Path):
        res = runner.invoke(
            manage,
            ["not_a_plugin", "-a", "search_internet::search:web:query", "--config", str(cfg)],
        )
        assert res.exit_code != 0
        assert "Plugin 'not_a_plugin'" in res.output

    def test_unknown_capability_warns(self, runner: CliRunner, cfg: Path):
        res = runner.invoke(
            manage,
            ["brave_search", "-a", "no_cap::x:y", "--config", str(cfg)],
        )
        assert res.exit_code == 0
        assert "Capability 'no_cap'" in res.output

    def test_no_flags_nop(self, runner: CliRunner, cfg: Path):
        res = runner.invoke(manage, ["brave_search", "--config", str(cfg)])
        assert res.exit_code == 0
        assert "Nothing to do" in res.output

    def test_multiple_adds_same_cap(self, runner: CliRunner, cfg: Path):
        res = runner.invoke(
            manage,
            [
                "brave_search",
                "-a",
                "search_internet::s:one",
                "-a",
                "search_internet::s:two",
                "--config",
                str(cfg),
            ],
        )
        assert res.exit_code == 0
        data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        scopes = data["plugins"]["brave_search"]["capabilities"]["search_internet"]["required_scopes"]
        assert {"s:one", "s:two"}.issubset(scopes)

    def test_config_path_not_found(self, runner: CliRunner, tmp_path: Path):
        missing = tmp_path / "missing.yml"
        res = runner.invoke(
            manage,
            ["brave_search", "-a", "search_internet::s:x", "--config", str(missing)],
        )
        assert res.exit_code != 0
        assert "Plugin 'brave_search' not found" in res.output

    def test_add_scope_to_empty_capability_dict(self, runner: CliRunner, cfg: Path):
        # Make capability node an empty dict {}
        data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        data["plugins"]["brave_search"]["capabilities"]["search_internet"] = {}
        cfg.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

        res = runner.invoke(
            manage,
            [
                "brave_search",
                "-a",
                "search_internet::added:scope",
                "--config",
                str(cfg),
            ],
        )
        assert res.exit_code == 0
        after = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        scopes = after["plugins"]["brave_search"]["capabilities"]["search_internet"].get("required_scopes", [])
        assert scopes == ["added:scope"]

    def test_remove_last_scope_results_empty_list(self, runner: CliRunner, cfg: Path):
        # Seed a single scope then remove it; we expect an empty dict to persist
        data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        data["plugins"]["brave_search"]["capabilities"]["search_internet"]["required_scopes"] = [
            "only:one"
        ]
        cfg.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

        res = runner.invoke(
            manage,
            ["brave_search", "-r", "search_internet::only:one", "--config", str(cfg)],
        )
        assert res.exit_code == 0
        after = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        assert after["plugins"]["brave_search"]["capabilities"]["search_internet"] == {}

 
    def test_handles_null_required_scopes_then_adds(self, runner: CliRunner, cfg: Path):
        data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        data["plugins"]["brave_search"]["capabilities"]["search_internet"] = {}
        cfg.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

        res = runner.invoke(
            manage,
            ["brave_search", "-a", "search_internet::z:y", "--config", str(cfg)],
        )
        assert res.exit_code == 0
        after = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        assert after["plugins"]["brave_search"]["capabilities"]["search_internet"]["required_scopes"] == [
            "z:y"
        ]

    def test_remove_when_required_scopes_missing_warns(self, runner: CliRunner, cfg: Path):
        # Make the capability an empty dict and try to remove a scope that isn't there
        data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
        data["plugins"]["brave_search"]["capabilities"]["search_internet"] = {}
        cfg.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

        res = runner.invoke(
            manage,
            ["brave_search", "-r", "search_internet::no:match", "--config", str(cfg)],
        )
        assert res.exit_code == 0
        assert "not found" in res.output
