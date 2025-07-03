import os
import subprocess  # nosec B404
import sys
from pathlib import Path

import click


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path("agent_config.yaml"),
    show_default=True,
    help="Path to your agent config file.",
)
@click.option(
    "--host",
    default="127.0.0.1",
    show_default=True,
    help="Host/IP to bind the server to.",
)
@click.option(
    "--port",
    "-p",
    type=click.IntRange(1, 65535),
    default=8000,
    show_default=True,
    help="Port to run on (1–65535).",
)
@click.option(
    "--reload/--no-reload",
    default=True,
    show_default=True,
    help="Enable or disable auto-reload.",
)
@click.version_option("1.0.0", prog_name="dev-server")
def dev(config: Path, host: str, port: int, reload: bool):
    """Start the development server."""
    click.echo(f"Using config: {config}")
    click.echo(f"Starting dev server at http://{host}:{port}  (reload={reload})")

    # Resolve project root: ensure config exists at given path
    if not config.exists():
        click.secho(f"❌ Config file not found: {config}", fg="red", err=True)
        sys.exit(1)

    # Detect execution context and determine the correct module path
    project_root = Path.cwd()
    local_main = project_root / "src" / "agent" / "main.py"

    # Prepare environment with proper PYTHONPATH and config path
    env = os.environ.copy()
    env["AGENT_CONFIG_PATH"] = str(config)

    if local_main.exists():
        # We're in a generated project - ensure Python can find the local modules
        app_module = "src.agent.main:app"
        click.echo(f"Running from local project at: {project_root}")

        # Add project root to PYTHONPATH
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{project_root}{os.pathsep}{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = str(project_root)

        click.echo(f"PYTHONPATH set to: {env.get('PYTHONPATH')}")

        # Build the Uvicorn command using Python module to ensure correct environment
        cmd = [sys.executable, "-m", "uvicorn", app_module, "--host", host, "--port", str(port)]
    else:
        # We're running from installed package or source repo
        app_module = "agent.api.app:app"
        click.echo("Running from installed package")

        # Build the Uvicorn command using Python module to ensure correct environment
        cmd = [sys.executable, "-m", "uvicorn", app_module, "--host", host, "--port", str(port)]

    if reload:
        cmd.append("--reload")

    click.echo(f"Running command: {' '.join(cmd)}")

    import signal

    # Start the subprocess in a new process group
    # Bandit: subprocess is used for legitimate command execution
    proc = subprocess.Popen(cmd, env=env, preexec_fn=os.setsid)  # nosec

    # Set up signal handlers to forward signals to the child process group
    def signal_handler(signum, frame):
        if proc.poll() is None:  # Process is still running
            try:
                # Send signal to the entire process group
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=5)  # Wait up to 5 seconds for graceful shutdown
            except subprocess.TimeoutExpired:
                # Force kill the process group if it doesn't terminate
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    proc.wait()
                except ProcessLookupError:
                    pass  # Process group already gone
            except ProcessLookupError:
                # Process already terminated
                pass
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Wait for the process to complete
        returncode = proc.wait()
        if returncode != 0:
            click.echo(f"Server exited with non-zero status: {returncode}")
            sys.exit(returncode)
    except KeyboardInterrupt:
        click.echo("👋 Shutting down gracefully...")
        signal_handler(signal.SIGINT, None)
    except Exception as e:
        click.echo(f"Unexpected error: {e}")
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
        sys.exit(1)
