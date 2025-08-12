import os
import platform
import subprocess  # nosec B404
import sys
from pathlib import Path

import click
import structlog

logger = structlog.get_logger(__name__)


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=Path("agentup.yml"),
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
@click.version_option("1.0.0", prog_name="agentup-run")
def run(config: Path, host: str, port: int, reload: bool):
    """Start the development server."""
    # import structlog

    # from agent.config.logging import setup_logging

    # # Setup logging for server operations
    # setup_logging()
    # logger = structlog.get_logger(__name__)

    logger.info("Starting AgentUp server", config=str(config), host=host, port=port, reload=reload)

    # Resolve project root: ensure config exists at given path
    if not config.exists():
        click.secho(f"✗ Config file not found: {config}", fg="red", err=True)
        sys.exit(1)

    # Note: Auto-install logic removed - users should use 'uv add <plugin>' + 'agentup plugin sync'

    logger.info("Starting server", host=host, port=port, reload=reload)

    # Always use framework mode - agents run from installed AgentUp package
    app_module = "agent.api.app:app"

    # Prepare environment with config path
    env = os.environ.copy()
    env["AGENT_CONFIG_PATH"] = str(config)

    # Build the Uvicorn command using Python module
    cmd = [sys.executable, "-m", "uvicorn", app_module, "--host", host, "--port", str(port)]

    if reload:
        cmd.append("--reload")

    logger.debug("Executing command", command=" ".join(cmd))

    import signal

    # Start the subprocess with proper signal handling
    # Bandit: subprocess is used for legitimate command execution
    if platform.system() == "Windows":
        # Windows doesn't support os.setsid
        proc = subprocess.Popen(cmd, env=env, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)  # nosec
    else:
        # Unix-like systems (macOS, Linux)
        proc = subprocess.Popen(cmd, env=env, preexec_fn=os.setsid)  # nosec

    # Signal handling with proper state management
    shutdown_in_progress = False

    def signal_handler(signum, frame):
        nonlocal shutdown_in_progress

        # Prevent multiple shutdown attempts
        if shutdown_in_progress:
            return
        shutdown_in_progress = True

        # Restore default signal handlers to prevent recursive calls
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)

        logger.info("Shutting down server")

        if proc.poll() is None:  # Process is still running
            try:
                if platform.system() == "Windows":
                    # Windows: terminate the process directly
                    proc.terminate()
                    proc.wait(timeout=3)
                else:
                    # Unix: send signal to the entire process group
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                # Force kill if it doesn't terminate gracefully
                logger.warning("Force stopping server")
                try:
                    if platform.system() == "Windows":
                        proc.kill()
                    else:
                        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                    proc.wait(timeout=1)
                except (subprocess.TimeoutExpired, ProcessLookupError):
                    pass  # Process is gone
            except ProcessLookupError:
                # Process already terminated
                pass

        logger.info("Server stopped")
        sys.exit(0)

    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Wait for the process to complete
        returncode = proc.wait()
        if returncode != 0:
            logger.error("Server exited with non-zero status", status=returncode)
            sys.exit(returncode)
    except KeyboardInterrupt:
        # Ctrl+C was pressed, signal handler should handle it
        signal_handler(signal.SIGINT, None)
    except Exception as e:
        logger.error("Unexpected error", error=str(e))
        signal_handler(signal.SIGTERM, None)
