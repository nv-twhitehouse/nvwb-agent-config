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
    "CLAUDE_BASE", "CLAUDE_OUT",
    "CODEX_BASE", "CODEX_OUT",
    "CODEX_HOOKS_BASE", "CODEX_HOOKS_OUT",
    "CACHED_POLICY", "CACHED_CLAUDE", "CACHED_CODEX",
    "MANAGED_BLOCKED", "MANAGED_ALLOWED", "AUDIT_LOG",
]


def _build_sandbox(tmpdir):
    root = Path(tmpdir)
    home = root / "home"
    agent = root / "agent-config"
    cache = root / "cache"

    (home / ".claude").mkdir(parents=True)
    (home / ".codex").mkdir(parents=True)
    (cache / "logs").mkdir(parents=True)

    claude_cfg = agent / "claude-config"
    codex_cfg = agent / "codex-config"
    claude_cfg.mkdir(parents=True)
    codex_cfg.mkdir(parents=True)

    shutil.copy2(os.path.join(REPO, "claude-config", "settings.json"), claude_cfg / "settings.json")
    shutil.copy2(os.path.join(REPO, "codex-config", "config.toml"), codex_cfg / "config.toml")
    shutil.copy2(os.path.join(REPO, "codex-config", "hooks.json"), codex_cfg / "hooks.json")
    shutil.copy2(os.path.join(REPO, "agentPolicyTemplate.yaml"), agent / "agentPolicyTemplate.yaml")

    originals = {k: getattr(renderPolicy, k) for k in _MODULE_CONSTANTS}

    renderPolicy.HOME_DIR = str(home)
    renderPolicy.AGENT_CONFIG_DIR = agent
    renderPolicy.CACHE_DIR = cache
    renderPolicy.CLAUDE_BASE = claude_cfg / "settings.json"
    renderPolicy.CLAUDE_OUT = home / ".claude" / "settings.json"
    renderPolicy.CODEX_BASE = codex_cfg / "config.toml"
    renderPolicy.CODEX_OUT = home / ".codex" / "config.toml"
    renderPolicy.CODEX_HOOKS_BASE = codex_cfg / "hooks.json"
    renderPolicy.CODEX_HOOKS_OUT = home / ".codex" / "hooks.json"
    renderPolicy.CACHED_POLICY = cache / "agentPolicyConfig.yaml"
    renderPolicy.CACHED_CLAUDE = cache / "claude-settings.json"
    renderPolicy.CACHED_CODEX = cache / "codex-config.toml"
    renderPolicy.MANAGED_BLOCKED = cache / "bypassBlocked.json"
    renderPolicy.MANAGED_ALLOWED = cache / "bypassAllowed.json"
    renderPolicy.AUDIT_LOG = cache / "logs" / "agent-audit.txt"

    return originals, str(agent / "agentPolicyTemplate.yaml")


def _restore(originals):
    for k, v in originals.items():
        setattr(renderPolicy, k, v)


def _render_all(policy_path):
    policy = renderPolicy.load_policy(policy_path)
    renderPolicy.render_claude(policy)
    renderPolicy.render_codex(policy)
    renderPolicy.seed_codex_hooks()
    renderPolicy.render_managed(policy)
    renderPolicy.save_cache(policy_path)


class TestPolicyChanged(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.originals, self.policy_path = _build_sandbox(self.tmpdir)

    def tearDown(self):
        _restore(self.originals)
        shutil.rmtree(self.tmpdir)

    def test_no_cache_returns_true(self):
        self.assertTrue(renderPolicy.policy_changed(self.policy_path))

    def test_same_content_returns_false(self):
        shutil.copy2(self.policy_path, renderPolicy.CACHED_POLICY)
        self.assertFalse(renderPolicy.policy_changed(self.policy_path))

    def test_different_content_returns_true(self):
        renderPolicy.CACHED_POLICY.write_text("old: content\n")
        self.assertTrue(renderPolicy.policy_changed(self.policy_path))


class TestNeedsRender(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.originals, self.policy_path = _build_sandbox(self.tmpdir)

    def tearDown(self):
        _restore(self.originals)
        shutil.rmtree(self.tmpdir)

    def test_no_cache_needs_render(self):
        self.assertTrue(renderPolicy.needs_render(self.policy_path))

    def test_unchanged_but_output_missing_needs_render(self):
        _render_all(self.policy_path)
        self.assertFalse(renderPolicy.needs_render(self.policy_path))

        renderPolicy.CODEX_OUT.unlink()
        self.assertTrue(renderPolicy.needs_render(self.policy_path))

    def test_unchanged_and_all_present_skips(self):
        _render_all(self.policy_path)
        self.assertFalse(renderPolicy.needs_render(self.policy_path))

    def test_missing_bootstrap_hooks_do_not_force_policy_render(self):
        _render_all(self.policy_path)

        renderPolicy.CODEX_HOOKS_OUT.unlink()
        self.assertFalse(renderPolicy.needs_render(self.policy_path))

    def test_dangling_bootstrap_hooks_do_not_force_policy_render(self):
        _render_all(self.policy_path)

        renderPolicy.CODEX_HOOKS_OUT.unlink()
        renderPolicy.CODEX_HOOKS_OUT.symlink_to("/nonexistent/target")
        self.assertFalse(renderPolicy.needs_render(self.policy_path))


class TestSaveCache(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.originals, self.policy_path = _build_sandbox(self.tmpdir)

    def tearDown(self):
        _restore(self.originals)
        shutil.rmtree(self.tmpdir)

    def test_copies_policy_and_outputs(self):
        _render_all(self.policy_path)
        self.assertTrue(renderPolicy.CACHED_POLICY.exists())
        self.assertTrue(renderPolicy.CACHED_CLAUDE.exists())
        self.assertTrue(renderPolicy.CACHED_CODEX.exists())

    def test_missing_output_skipped(self):
        policy = renderPolicy.load_policy(self.policy_path)
        renderPolicy.render_claude(policy)
        renderPolicy.save_cache(self.policy_path)
        self.assertTrue(renderPolicy.CACHED_CLAUDE.exists())
        self.assertFalse(renderPolicy.CACHED_CODEX.exists())


if __name__ == "__main__":
    unittest.main()
