"""Project-local compatibility fixes for Benchflow 0.6.5's Pi adapter.

Run with the Python interpreter belonging to the installed bench CLI.
No installed Benchflow files are modified.
"""

from dataclasses import replace


PI_VERSION = "1.0.0"
PI_ACP_VERSION = "0.0.34"


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


if __name__ == "__main__":
    configure_pi()
    from benchflow.cli.main import app

    app()
