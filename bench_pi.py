"""Project-local fixes for Benchflow 0.6.5's Pi adapter and OpenRouter routing.

Run with the Python interpreter belonging to the installed bench CLI.
No installed Benchflow files are modified.
"""

import shlex
import sys
from dataclasses import replace


PI_VERSION = "1.0.0"
PI_ACP_VERSION = "0.0.34"

# OpenRouter's default routing sent 78% of the 2026-10-02 Pi run to Relace,
# which bills cached input at the full input price and output at 10x
# StreamLake's rate. Prefer StreamLake; fallbacks stay on for its outages.
OPENROUTER_PROVIDER = {"order": ["StreamLake"], "ignore": ["Relace"]}


def configure_pi():
    from benchflow.agents import registry

    config = registry.AGENTS["pi-acp"]
    install = config.install_cmd
    packages = [
        ("pi", "@mariozechner/pi-coding-agent",
         f"@earendil-works/pi-coding-agent@{PI_VERSION}"),
        ("pi-acp", "pi-acp", f"pi-acp@{PI_ACP_VERSION}"),
    ]
    for binary, old_package, new_package in packages:
        # Rebuild the install fragment too: the unversioned installer skips
        # existing binaries, whereas a pinned install must replace old copies.
        old = registry._js_agent_install(binary, old_package)
        new = registry._js_agent_install(binary, new_package)
        if old not in install:
            raise RuntimeError(
                f"Benchflow's Pi installer changed ({old_package}); review bench_pi.py"
            )
        install = install.replace(old, new)
    config = replace(
        config,
        install_cmd=install,
        acp_model_config_id="model",
        acp_effort_config_id="thought_level",
    )
    registry.AGENTS[config.name] = config
    registry.AGENT_INSTALLERS[config.name] = config.install_cmd
    registry.AGENT_LAUNCH[config.name] = config.launch_cmd
    return config


def pin_openrouter_provider():
    """Add OpenRouter provider preferences to the LiteLLM proxy config."""
    from benchflow.providers import litellm_runtime

    build = litellm_runtime.litellm_proxy_config

    def pinned(route, **kwargs):
        config = build(route, **kwargs)
        if route.provider_name == "openrouter":
            for entry in config["model_list"]:
                entry["litellm_params"]["extra_body"] = {"provider": OPENROUTER_PROVIDER}
        return config

    litellm_runtime.litellm_proxy_config = pinned


def skip_sandbox_pytest_plugins():
    """Force-load only declared pytest plugins, not ones found in the sandbox.

    Benchflow passes `-p <name>` for every pytest11 entry point in the
    container, assuming a non-root agent could not have installed any. A root
    agent can: on TB2 a pip-installed typeguard plugin crashed the verifier's
    isolated uvx pytest ("Error importing plugin") and scored a solved task 0.
    """
    from benchflow.sandbox import lockdown

    async def declared_only(env, task):
        names = [*task.config.verifier.pytest_plugins,
                 *lockdown._infer_pytest_plugins_from_test_script(task)]
        return " ".join(f"-p {shlex.quote(n)}" for n in dict.fromkeys(names))

    lockdown._discover_pytest_plugin_flags = declared_only


MIN_EXEC_TIMEOUT_SEC = 120


def tolerate_slow_docker():
    """Give benchflow's short housekeeping execs time to finish.

    The Docker daemon stalls for seconds while other rollouts pull or delete
    multi-GB images. A 10s `mkdir -p /logs/agent` before verification then
    times out and the finished run is discarded unscored (3 of the first 22
    TB2 baseline runs). Agent tool calls do not go through this method.
    """
    from benchflow.sandbox.docker import DockerSandbox

    exec_ = DockerSandbox.exec

    async def patient_exec(self, command, cwd=None, env=None, timeout_sec=None,
                           user=None, service="main"):
        if timeout_sec is not None:
            timeout_sec = max(timeout_sec, MIN_EXEC_TIMEOUT_SEC)
        return await exec_(self, command, cwd=cwd, env=env, timeout_sec=timeout_sec,
                           user=user, service=service)

    DockerSandbox.exec = patient_exec


def runs_as_root(argv):
    return "--sandbox-user" in argv and argv[argv.index("--sandbox-user") + 1] == "none"


if __name__ == "__main__":
    configure_pi()
    pin_openrouter_provider()
    tolerate_slow_docker()
    if runs_as_root(sys.argv):
        skip_sandbox_pytest_plugins()
    from benchflow.cli.main import app

    app()
