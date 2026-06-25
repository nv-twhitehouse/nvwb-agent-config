import os
import sys
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "scripts"))

import renderPolicy


class TestUnion(unittest.TestCase):
    def test_basic_dedup(self):
        self.assertEqual(renderPolicy.union(["a", "b"], ["b", "c"]), ["a", "b", "c"])

    def test_preserves_order(self):
        self.assertEqual(renderPolicy.union(["z", "a"], ["m", "a"]), ["z", "a", "m"])

    def test_empty_inputs(self):
        self.assertEqual(renderPolicy.union([], []), [])


class TestDeepMerge(unittest.TestCase):
    def test_overlay_wins_scalar(self):
        result = renderPolicy.deep_merge({"a": 1}, {"a": 2})
        self.assertEqual(result["a"], 2)

    def test_nested_dicts_merge(self):
        base = {"a": {"x": 1, "y": 2}}
        overlay = {"a": {"y": 3, "z": 4}}
        result = renderPolicy.deep_merge(base, overlay)
        self.assertEqual(result["a"], {"x": 1, "y": 3, "z": 4})

    def test_overlay_replaces_list(self):
        result = renderPolicy.deep_merge({"a": [1, 2]}, {"a": [3]})
        self.assertEqual(result["a"], [3])

    def test_disjoint_keys(self):
        result = renderPolicy.deep_merge({"a": 1}, {"b": 2})
        self.assertEqual(result, {"a": 1, "b": 2})

    def test_base_not_mutated(self):
        base = {"a": {"x": 1}}
        renderPolicy.deep_merge(base, {"a": {"y": 2}})
        self.assertEqual(base, {"a": {"x": 1}})


class TestToTilde(unittest.TestCase):
    def test_home_prefix_replaced(self):
        self.assertEqual(renderPolicy.to_tilde("/home/workbench/.claude"), "~/.claude")

    def test_non_home_unchanged(self):
        self.assertEqual(renderPolicy.to_tilde("/etc/foo"), "/etc/foo")


class TestDenyRules(unittest.TestCase):
    def test_normal_path(self):
        rules = renderPolicy._deny_rules("/etc/foo", ("Read", "Write"))
        self.assertIn("Read(//etc/foo)", rules)
        self.assertIn("Read(//etc/foo/**)", rules)
        self.assertIn("Write(//etc/foo)", rules)
        self.assertIn("Write(//etc/foo/**)", rules)

    def test_glob_path_skips_double_star(self):
        rules = renderPolicy._deny_rules("/home/workbench/.codex/*.sqlite", ("Read",))
        self.assertIn("Read(//home/workbench/.codex/*.sqlite)", rules)
        self.assertNotIn("Read(//home/workbench/.codex/*.sqlite/**)", rules)


class TestBuildClaudeOverlay(unittest.TestCase):
    def _minimal_policy(self, **overrides):
        policy = {
            "paths": {"write": [], "read_only": [], "private": []},
            "commands": {"ask": [], "deny": []},
        }
        policy.update(overrides)
        return policy

    def test_write_paths_become_additional_directories(self):
        policy = self._minimal_policy(paths={"write": ["/project", "/tmp"], "read_only": [], "private": []})
        overlay = renderPolicy.build_claude_overlay(policy)
        dirs = overlay["permissions"]["additionalDirectories"]
        self.assertIn("/project/", dirs)
        self.assertIn("/tmp/", dirs)
        self.assertIn("~/", dirs)

    def test_commands_become_bash_patterns(self):
        policy = self._minimal_policy(commands={"ask": ["git add"], "deny": ["sudo"]})
        overlay = renderPolicy.build_claude_overlay(policy)
        self.assertIn("Bash(git add *)", overlay["permissions"]["ask"])
        self.assertIn("Bash(sudo *)", overlay["permissions"]["deny"])

    def test_private_paths_in_both_deny_lists(self):
        policy = self._minimal_policy(paths={"write": [], "read_only": [], "private": ["/home/workbench/.secret"]})
        overlay = renderPolicy.build_claude_overlay(policy)
        self.assertIn("~/.secret", overlay["sandbox"]["filesystem"]["denyWrite"])
        self.assertIn("~/.secret", overlay["sandbox"]["filesystem"]["denyRead"])

    def test_read_only_in_deny_write_only(self):
        policy = self._minimal_policy(paths={"write": [], "read_only": ["/home/workbench/.config"], "private": []})
        overlay = renderPolicy.build_claude_overlay(policy)
        self.assertIn("~/.config", overlay["sandbox"]["filesystem"]["denyWrite"])
        self.assertNotIn("~/.config", overlay["sandbox"]["filesystem"]["denyRead"])


class TestBuildCodexOverlay(unittest.TestCase):
    def _minimal_policy(self, **overrides):
        policy = {
            "paths": {"write": [], "read_only": [], "private": [], "private_project_patterns": []},
            "environment": {"private_names": [], "private_patterns": []},
        }
        policy.update(overrides)
        return policy

    def test_workspace_roots(self):
        policy = self._minimal_policy(paths={"write": ["/project"], "read_only": [], "private": [], "private_project_patterns": []})
        overlay = renderPolicy.build_codex_overlay(policy)
        self.assertEqual(overlay["permissions"]["nvwb_workspace"]["workspace_roots"]["/project"], True)

    def test_read_only_filesystem_rules(self):
        policy = self._minimal_policy(paths={"write": [], "read_only": ["/home/workbench/.codex"], "private": [], "private_project_patterns": []})
        overlay = renderPolicy.build_codex_overlay(policy)
        self.assertEqual(overlay["permissions"]["nvwb_workspace"]["filesystem"]["~/.codex"], "read")

    def test_private_filesystem_rules(self):
        policy = self._minimal_policy(paths={"write": [], "read_only": [], "private": ["/home/workbench/.codex/auth.json"], "private_project_patterns": []})
        overlay = renderPolicy.build_codex_overlay(policy)
        self.assertEqual(overlay["permissions"]["nvwb_workspace"]["filesystem"]["~/.codex/auth.json"], "deny")

    def test_environment_exclude_merged(self):
        policy = self._minimal_policy(environment={"private_names": ["FOO"], "private_patterns": ["BAR_*"]})
        overlay = renderPolicy.build_codex_overlay(policy)
        exclude = overlay["shell_environment_policy"]["exclude"]
        self.assertIn("FOO", exclude)
        self.assertIn("BAR_*", exclude)


class TestBuildManagedOverlay(unittest.TestCase):
    def _minimal_policy(self):
        return {
            "paths": {"read_only": ["/project/.project"], "private": ["/home/workbench/.secret"]},
            "commands": {"deny": ["sudo"]},
        }

    def test_bypass_blocked_has_disable_flags(self):
        overlay = renderPolicy.build_managed_overlay(self._minimal_policy(), bypass_blocked=True)
        self.assertEqual(overlay["permissions"]["disableBypassPermissionsMode"], "disable")
        self.assertEqual(overlay["permissions"]["disableAutoMode"], "disable")

    def test_bypass_allowed_lacks_disable_flags(self):
        overlay = renderPolicy.build_managed_overlay(self._minimal_policy(), bypass_blocked=False)
        self.assertNotIn("disableBypassPermissionsMode", overlay["permissions"])
        self.assertNotIn("disableAutoMode", overlay["permissions"])

    def test_deny_rules_from_read_only(self):
        overlay = renderPolicy.build_managed_overlay(self._minimal_policy(), bypass_blocked=False)
        deny = overlay["permissions"]["deny"]
        self.assertIn("Edit(//project/.project)", deny)
        self.assertIn("Write(//project/.project)", deny)
        self.assertNotIn("Read(//project/.project)", deny)

    def test_deny_rules_from_private(self):
        overlay = renderPolicy.build_managed_overlay(self._minimal_policy(), bypass_blocked=False)
        deny = overlay["permissions"]["deny"]
        self.assertIn("Read(//home/workbench/.secret)", deny)
        self.assertIn("Edit(//home/workbench/.secret)", deny)
        self.assertIn("Write(//home/workbench/.secret)", deny)

    def test_deny_commands(self):
        overlay = renderPolicy.build_managed_overlay(self._minimal_policy(), bypass_blocked=False)
        self.assertIn("Bash(sudo *)", overlay["permissions"]["deny"])


class TestHookRewriting(unittest.TestCase):
    def test_rewrite_with_match(self):
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            hooks_dir = Path(d)
            sub = hooks_dir / "ai-workbench-container"
            sub.mkdir()
            (sub / "start.sh").write_text("#!/bin/bash\n")

            hook_paths = renderPolicy._hook_relative_paths(hooks_dir)
            cmd = "$HOME/.codex/hooks/start.sh"
            rewritten, changed = renderPolicy._rewrite_hook_command(cmd, hook_paths, hooks_dir, ".codex")
            self.assertTrue(changed)
            self.assertIn("ai-workbench-container/start.sh", rewritten)

    def test_no_match_passthrough(self):
        cmd = "/usr/bin/env bash"
        rewritten, changed = renderPolicy._rewrite_hook_command(cmd, {}, None, ".codex")
        self.assertFalse(changed)
        self.assertEqual(rewritten, cmd)

    def test_recursive_json_walk(self):
        structure = {
            "hooks": {
                "SessionStart": [
                    {"command": "$HOME/.codex/hooks/start.sh", "type": "command"}
                ]
            }
        }
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            hooks_dir = Path(d)
            sub = hooks_dir / "sub"
            sub.mkdir()
            (sub / "start.sh").write_text("#!/bin/bash\n")
            hook_paths = renderPolicy._hook_relative_paths(hooks_dir)

            rewritten, count = renderPolicy._rewrite_hooks_json(structure, hook_paths, hooks_dir, ".codex")
            self.assertEqual(count, 1)
            self.assertIn("sub/start.sh", rewritten["hooks"]["SessionStart"][0]["command"])


if __name__ == "__main__":
    unittest.main()
