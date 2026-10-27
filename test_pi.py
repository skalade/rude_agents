"""Offline integration checks; run with the installed Benchflow Python."""

import json
import unittest
from argparse import Namespace

import bench_pi
import experiment
from benchflow.agents import registry
from benchflow.providers.litellm_config import resolve_litellm_route
from benchflow.providers.litellm_runtime import _provider_models_for_proxy_alias


class PiIntegrationTests(unittest.TestCase):
    def test_installer_and_acp_contract(self):
        original = registry.AGENTS["pi-acp"]
        other = registry.AGENTS["opencode"]
        try:
            config = bench_pi.configure_pi()
            self.assertEqual(config.acp_effort_config_id, "thought_level")
            self.assertEqual(config.acp_model_config_id, "model")
            self.assertIn("@earendil-works/pi-coding-agent@1.0.0", config.install_cmd)
            self.assertIn("pi-acp@0.0.34", config.install_cmd)
            self.assertNotIn("@mariozechner", config.install_cmd)
            self.assertNotIn(" ] || ", config.install_cmd)
            self.assertIs(registry.AGENTS["opencode"], other)
            self.assertEqual(registry.AGENT_INSTALLERS["pi-acp"], config.install_cmd)
        finally:
            registry.AGENTS["pi-acp"] = original
            registry.AGENT_INSTALLERS["pi-acp"] = original.install_cmd
            registry.AGENT_LAUNCH["pi-acp"] = original.launch_cmd

    def test_reasoning_metadata_survives_gateway_alias(self):
        for effort in experiment.REASONING_EFFORTS:
            args = experiment.reasoning_args("pi", experiment.AGENTS["pi"], effort)
            self.assertEqual(args[:2], ["--reasoning-effort", effort])
            raw = args[-1].split("=", 1)[1]
            route = resolve_litellm_route(
                model=experiment.AGENTS["pi"], env={"OPENROUTER_API_KEY": "test"}
            )
            aliased = json.loads(_provider_models_for_proxy_alias(raw=raw, route=route))
            model = next(m for m in aliased if m["id"] == route.model_alias)
            self.assertTrue(model["reasoning"])
            self.assertEqual(model["maxTokens"], 384000)
            self.assertEqual(model["contextWindow"], 1024000)

    def test_grid_and_retry_keep_pi_configuration(self):
        args = Namespace(agent="pi", model=None, sandbox="docker",
                         skill_mode="with-skill", concurrency=2, reasoning_effort="high")
        commands = [experiment.bench_command(args, c, t)
                    for t in range(1, 4) for c in experiment.CONDITIONS]
        self.assertEqual(len(commands), 12)
        roots = {c[c.index("--jobs-dir") + 1] for c in commands}
        self.assertEqual(len(roots), 12)
        self.assertTrue(all("/jobs/pi/" in root for root in roots))
        retry = experiment.retry_bench_command(
            args, "baseline", 1, "dialogue-parser", "/tmp/pi-test-retry"
        )
        self.assertEqual(retry[1], str(experiment.ROOT / "bench_pi.py"))
        self.assertEqual(retry[retry.index("--reasoning-effort") + 1], "high")
        self.assertEqual(retry[retry.index("--concurrency") + 1], "1")

    def test_unknown_pi_metadata_fails_closed(self):
        with self.assertRaises(SystemExit):
            experiment.reasoning_args("pi", "openrouter/unknown/model", "high")

    def test_openrouter_provider_pinned_in_proxy_config(self):
        from benchflow.providers import litellm_runtime

        original = litellm_runtime.litellm_proxy_config
        try:
            bench_pi.pin_openrouter_provider()
            route = resolve_litellm_route(
                model=experiment.AGENTS["pi"], env={"OPENROUTER_API_KEY": "test"}
            )
            config = litellm_runtime.litellm_proxy_config(route, master_key="k")
            for entry in config["model_list"]:
                self.assertEqual(
                    entry["litellm_params"]["extra_body"],
                    {"provider": bench_pi.OPENROUTER_PROVIDER},
                )
        finally:
            litellm_runtime.litellm_proxy_config = original


class SlowDockerTests(unittest.TestCase):
    def test_short_exec_timeouts_raised_long_ones_kept(self):
        import asyncio

        from benchflow.sandbox.docker import DockerSandbox

        original = DockerSandbox.exec
        seen = []

        async def fake_exec(self, command, cwd=None, env=None, timeout_sec=None,
                            user=None, service="main"):
            seen.append(timeout_sec)

        try:
            DockerSandbox.exec = fake_exec
            bench_pi.tolerate_slow_docker()
            for timeout in (10, 900, None):
                asyncio.run(DockerSandbox.exec(object(), "mkdir -p /logs/agent",
                                               user="root", timeout_sec=timeout))
        finally:
            DockerSandbox.exec = original
        self.assertEqual(seen, [bench_pi.MIN_EXEC_TIMEOUT_SEC, 900, None])


class Tb2Tests(unittest.TestCase):
    def setUp(self):
        experiment.use_bench("tb2")

    def tearDown(self):
        experiment.use_bench("skillsbench")

    def test_command_runs_as_root_without_skills(self):
        args = Namespace(agent="pi", model=None, sandbox="docker",
                         skill_mode=None, concurrency=2, reasoning_effort="high")
        cmd = experiment.bench_command(args, "baseline", 1)
        self.assertEqual(cmd[cmd.index("--sandbox-user") + 1], "none")
        self.assertEqual(cmd[cmd.index("--skill-mode") + 1], "no-skill")
        self.assertIn("/build_tb2/baseline", cmd[cmd.index("--tasks-dir") + 1])
        self.assertIn("/jobs_tb2/pi/baseline/t1", cmd[cmd.index("--jobs-dir") + 1])

    def test_selected_tasks_exist(self):
        for name in experiment.selected_tasks():
            self.assertGreater(experiment.task_metadata(name)["timeout"], 0)

    def test_prompt_matches_condition(self):
        import tempfile
        from pathlib import Path

        task = "Fix the repo."
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            for sent_as in experiment.CONDITIONS:
                phrase = experiment.CONDITIONS[sent_as]
                prompt = f"{phrase}\n\n{task}" if phrase else task
                (run_dir / "prompts.json").write_text(json.dumps([prompt]))
                for labelled in experiment.CONDITIONS:
                    self.assertEqual(
                        experiment.prompt_matches(labelled, run_dir),
                        labelled == sent_as,
                        (sent_as, labelled),
                    )

    def test_phrase_prepended_to_instruction(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            prompt = Path(tmp) / "instruction.md"
            prompt.write_text("Fix the repo.\n")
            experiment.inject_phrase(prompt, "Be nice.")
            self.assertEqual(prompt.read_text(), "Be nice.\n\nFix the repo.\n")

    def test_root_runs_ignore_sandbox_pytest_plugins(self):
        import asyncio
        from pathlib import Path
        from types import SimpleNamespace

        from benchflow.sandbox import lockdown

        class NoExec:
            async def exec(self, *args, **kwargs):
                raise AssertionError("sandbox plugin discovery should be skipped")

        task = SimpleNamespace(
            config=SimpleNamespace(verifier=SimpleNamespace(pytest_plugins=[])),
            task_dir=Path(experiment.TASKS_ROOT / "build-pmars"),
        )
        original = lockdown._discover_pytest_plugin_flags
        try:
            bench_pi.skip_sandbox_pytest_plugins()
            flags = asyncio.run(lockdown._discover_pytest_plugin_flags(NoExec(), task))
            self.assertEqual(flags, "-p ctrf")
        finally:
            lockdown._discover_pytest_plugin_flags = original
        self.assertTrue(bench_pi.runs_as_root(["x", "--sandbox-user", "none"]))
        self.assertFalse(bench_pi.runs_as_root(["x", "--sandbox-user", "agent"]))
        self.assertFalse(bench_pi.runs_as_root(["x"]))

    def test_shebangless_test_script_gets_bash(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            bare, bash = Path(tmp) / "bare.sh", Path(tmp) / "bash.sh"
            bare.write_text("# canary\nsource $HOME/.local/bin/env\n")
            bash.write_text("#!/bin/bash\necho hi\n")
            for script in (bare, bash):
                experiment.ensure_bash_shebang(script)
            self.assertEqual(bare.read_text(), "#!/bin/bash\n# canary\nsource $HOME/.local/bin/env\n")
            self.assertEqual(bash.read_text(), "#!/bin/bash\necho hi\n")
            experiment.ensure_bash_shebang(Path(tmp) / "missing.sh")  # no-op

    def test_namespaced_task_name(self):
        result = {"task_name": "terminal-bench/fix-git"}
        self.assertEqual(experiment.task_name_for(result, None), "fix-git")


if __name__ == "__main__":
    unittest.main()
