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


if __name__ == "__main__":
    unittest.main()
