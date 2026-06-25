import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import renderPolicy

_MODULE_CONSTANTS = [
    "HOME_DIR", "AGENT_CONFIG_DIR", "CACHE_DIR",
    "CLAUDE_BASE", "CLAUDE_HOOKS_DIR", "CLAUDE_OUT",
    "CODEX_BASE", "CODEX_OUT",
    "CODEX_HOOKS_BASE", "CODEX_HOOKS_DIR", "CODEX_HOOKS_OUT",
    "CACHED_POLICY", "CACHED_CLAUDE", "CACHED_CODEX", "CACHED_CODEX_HOOKS",
    "MANAGED_BLOCKED", "MANAGED_ALLOWED", "AUDIT_LOG",
]


def _build_sandbox(tmpdir):
    """Create an isolated filesystem tree and patch renderPolicy constants."""
    root = Path(tmpdir)
    home = root / "home"
    agent = root / "agent-config"
    cache = root / "cache"

    (home / ".claude").mkdir(parents=True)
    (home / ".codex").mkdir(parents=True)
    (cache / "logs").mkdir(parents=True)

    claude_cfg = agent / "claude-config"
    codex_cfg = agent / "codex-config"
    (claude_cfg / "hooks" / "ai-workbench-container").mkdir(parents=True)
    (codex_cfg / "hooks" / "ai-workbench-container").mkdir(parents=True)

    shutil.copy2(os.path.join(REPO, "claude-config", "settings.json"), claude_cfg / "settings.json")
    shutil.copy2(os.path.join(REPO, "codex-config", "config.toml"), codex_cfg / "config.toml")
    shutil.copy2(os.path.join(REPO, "codex-config", "hooks.json"), codex_cfg / "hooks.json")
    shutil.copy2(os.path.join(REPO, "agentPolicyTemplate.yaml"), agent / "agentPolicyTemplate.yaml")

    for name in ("SessionStart-claude.sh", "SessionEnd-claude.sh"):
        p = claude_cfg / "hooks" / "ai-workbench-container" / name
        p.write_text("#!/bin/bash\nexit 0\n")

    p = codex_cfg / "hooks" / "ai-workbench-container" / "SessionStart-codex.sh"
    p.write_text("#!/bin/bash\nexit 0\n")

    originals = {k: getattr(renderPolicy, k) for k in _MODULE_CONSTANTS}

    renderPolicy.HOME_DIR = str(home)
    renderPolicy.AGENT_CONFIG_DIR = agent
    renderPolicy.CACHE_DIR = cache
    renderPolicy.CLAUDE_BASE = claude_cfg / "settings.json"
    renderPolicy.CLAUDE_HOOKS_DIR = claude_cfg / "hooks"
    renderPolicy.CLAUDE_OUT = home / ".claude" / "settings.json"
    renderPolicy.CODEX_BASE = codex_cfg / "config.toml"
    renderPolicy.CODEX_OUT = home / ".codex" / "config.toml"
    renderPolicy.CODEX_HOOKS_BASE = codex_cfg / "hooks.json"
    renderPolicy.CODEX_HOOKS_DIR = codex_cfg / "hooks"
    renderPolicy.CODEX_HOOKS_OUT = home / ".codex" / "hooks.json"
    renderPolicy.CACHED_POLICY = cache / "agentPolicyConfig.yaml"
    renderPolicy.CACHED_CLAUDE = cache / "claude-settings.json"
    renderPolicy.CACHED_CODEX = cache / "codex-config.toml"
    renderPolicy.CACHED_CODEX_HOOKS = cache / "codex-hooks.json"
    renderPolicy.MANAGED_BLOCKED = cache / "bypassBlocked.json"
    renderPolicy.MANAGED_ALLOWED = cache / "bypassAllowed.json"
    renderPolicy.AUDIT_LOG = cache / "logs" / "agent-audit.txt"

    policy = renderPolicy.load_policy(str(agent / "agentPolicyTemplate.yaml"))
    return originals, policy


def _restore(originals):
    for k, v in originals.items():
        setattr(renderPolicy, k, v)


class TestRenderClaude(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.originals, self.policy = _build_sandbox(self.tmpdir)

    def tearDown(self):
        _restore(self.originals)
        shutil.rmtree(self.tmpdir)

    def test_renders_valid_json(self):
        renderPolicy.render_claude(self.policy)
        out = renderPolicy.CLAUDE_OUT
        self.assertTrue(out.exists())
        with open(out) as f:
            data = json.load(f)
        self.assertIn("permissions", data)
        self.assertIn("sandbox", data)
        self.assertIn("hooks", data)

    def test_policy_permissions_merged(self):
        renderPolicy.render_claude(self.policy)
        with open(renderPolicy.CLAUDE_OUT) as f:
            data = json.load(f)
        deny = data["permissions"]["deny"]
        self.assertTrue(any("sudo" in r for r in deny))


class TestRenderCodex(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.originals, self.policy = _build_sandbox(self.tmpdir)

    def tearDown(self):
        _restore(self.originals)
        shutil.rmtree(self.tmpdir)

    def test_renders_valid_toml(self):
        import tomli
        renderPolicy.render_codex(self.policy)
        out = renderPolicy.CODEX_OUT
        self.assertTrue(out.exists())
        with open(out, "rb") as f:
            data = tomli.loads(f.read().decode())
        self.assertIn("permissions", data)
        self.assertIn("shell_environment_policy", data)

    def test_env_excludes_present(self):
        import tomli
        renderPolicy.render_codex(self.policy)
        with open(renderPolicy.CODEX_OUT, "rb") as f:
            data = tomli.loads(f.read().decode())
        exclude = data["shell_environment_policy"]["exclude"]
        self.assertIn("NVIDIA_API_KEY", exclude)


class TestRenderCodexHooks(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.originals, self.policy = _build_sandbox(self.tmpdir)

    def tearDown(self):
        _restore(self.originals)
        shutil.rmtree(self.tmpdir)

    def test_renders_valid_json(self):
        renderPolicy.render_codex_hooks(self.policy)
        out = renderPolicy.CODEX_HOOKS_OUT
        self.assertTrue(out.exists())
        with open(out) as f:
            data = json.load(f)
        self.assertIn("hooks", data)

    def test_output_is_regular_file(self):
        renderPolicy.render_codex_hooks(self.policy)
        out = renderPolicy.CODEX_HOOKS_OUT
        self.assertFalse(out.is_symlink())
        self.assertTrue(out.is_file())


class TestRenderManaged(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.originals, self.policy = _build_sandbox(self.tmpdir)

    def tearDown(self):
        _restore(self.originals)
        shutil.rmtree(self.tmpdir)

    def test_stages_both_variants(self):
        renderPolicy.render_managed(self.policy)
        self.assertTrue(renderPolicy.MANAGED_BLOCKED.exists())
        self.assertTrue(renderPolicy.MANAGED_ALLOWED.exists())

    def test_blocked_has_disable_flags(self):
        renderPolicy.render_managed(self.policy)
        with open(renderPolicy.MANAGED_BLOCKED) as f:
            data = json.load(f)
        self.assertEqual(data["permissions"]["disableBypassPermissionsMode"], "disable")
        self.assertEqual(data["permissions"]["disableAutoMode"], "disable")

    def test_allowed_lacks_disable_flags(self):
        renderPolicy.render_managed(self.policy)
        with open(renderPolicy.MANAGED_ALLOWED) as f:
            data = json.load(f)
        self.assertNotIn("disableBypassPermissionsMode", data["permissions"])


class TestFullPipeline(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.originals, self.policy = _build_sandbox(self.tmpdir)

    def tearDown(self):
        _restore(self.originals)
        shutil.rmtree(self.tmpdir)

    def test_all_outputs_created(self):
        renderPolicy.render_claude(self.policy)
        renderPolicy.render_codex(self.policy)
        renderPolicy.render_codex_hooks(self.policy)
        renderPolicy.render_managed(self.policy)

        self.assertTrue(renderPolicy.CLAUDE_OUT.exists())
        self.assertTrue(renderPolicy.CODEX_OUT.exists())
        self.assertTrue(renderPolicy.CODEX_HOOKS_OUT.exists())
        self.assertTrue(renderPolicy.MANAGED_BLOCKED.exists())
        self.assertTrue(renderPolicy.MANAGED_ALLOWED.exists())

    def test_dangling_symlink_handled(self):
        out = renderPolicy.CODEX_HOOKS_OUT
        out.symlink_to("/nonexistent/target/hooks.json")
        self.assertTrue(out.is_symlink())
        self.assertFalse(out.exists())

        renderPolicy.render_codex_hooks(self.policy)
        self.assertTrue(out.exists())
        self.assertFalse(out.is_symlink())

    def test_dangling_symlink_does_not_block_managed(self):
        renderPolicy.CODEX_HOOKS_OUT.symlink_to("/nonexistent/target/hooks.json")

        renderPolicy.render_claude(self.policy)
        renderPolicy.render_codex(self.policy)
        renderPolicy.render_codex_hooks(self.policy)
        renderPolicy.render_managed(self.policy)

        self.assertTrue(renderPolicy.MANAGED_BLOCKED.exists())
        self.assertTrue(renderPolicy.MANAGED_ALLOWED.exists())

    def test_missing_hooks_base_skips(self):
        renderPolicy.CODEX_HOOKS_BASE.unlink()

        renderPolicy.render_codex_hooks(self.policy)
        self.assertFalse(renderPolicy.CODEX_HOOKS_OUT.exists())

        renderPolicy.render_managed(self.policy)
        self.assertTrue(renderPolicy.MANAGED_BLOCKED.exists())


class TestDenyPlaceholders(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.originals, self.policy = _build_sandbox(self.tmpdir)
        self.home = Path(self.tmpdir) / "home"

    def tearDown(self):
        _restore(self.originals)
        shutil.rmtree(self.tmpdir)

    def _policy_with(self, read_only, private):
        p = dict(self.policy)
        p["paths"] = dict(p.get("paths", {}))
        p["paths"]["read_only"] = read_only
        p["paths"]["private"] = private
        return p

    def test_creates_missing_file_under_read_only_parent(self):
        claude_dir = self.home / ".claude"
        creds = str(claude_dir / "credentials.json")
        policy = self._policy_with(
            read_only=[str(claude_dir)],
            private=[creds],
        )
        self.assertFalse(Path(creds).exists())
        renderPolicy.ensure_deny_placeholders(policy)
        self.assertTrue(Path(creds).exists())
        self.assertTrue(Path(creds).is_file())

    def test_creates_missing_dir_under_read_only_parent(self):
        codex_dir = self.home / ".codex"
        sessions = str(codex_dir / "sessions")
        policy = self._policy_with(
            read_only=[str(codex_dir)],
            private=[sessions],
        )
        renderPolicy.ensure_deny_placeholders(policy)
        self.assertTrue(Path(sessions).exists())
        self.assertTrue(Path(sessions).is_dir())

    def test_skips_globs(self):
        codex_dir = self.home / ".codex"
        policy = self._policy_with(
            read_only=[str(codex_dir)],
            private=[str(codex_dir / "*.sqlite")],
        )
        renderPolicy.ensure_deny_placeholders(policy)
        self.assertFalse(list(codex_dir.glob("*.sqlite")))

    def test_skips_when_not_under_read_only(self):
        target = self.home / "some_file.json"
        policy = self._policy_with(
            read_only=[],
            private=[str(target)],
        )
        renderPolicy.ensure_deny_placeholders(policy)
        self.assertFalse(target.exists())

    def test_skips_already_existing(self):
        claude_dir = self.home / ".claude"
        creds = claude_dir / "credentials.json"
        creds.write_text("existing")
        policy = self._policy_with(
            read_only=[str(claude_dir)],
            private=[str(creds)],
        )
        renderPolicy.ensure_deny_placeholders(policy)
        self.assertEqual(creds.read_text(), "existing")

    def test_clears_dangling_symlink_and_creates_placeholder(self):
        claude_dir = self.home / ".claude"
        creds = claude_dir / "credentials.json"
        creds.symlink_to("/nonexistent/target")
        self.assertTrue(creds.is_symlink())
        self.assertFalse(creds.exists())

        policy = self._policy_with(
            read_only=[str(claude_dir)],
            private=[str(creds)],
        )
        renderPolicy.ensure_deny_placeholders(policy)
        self.assertTrue(creds.exists())
        self.assertFalse(creds.is_symlink())


if __name__ == "__main__":
    unittest.main()
