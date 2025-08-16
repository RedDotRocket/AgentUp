import subprocess  # nosec
from pathlib import Path


def get_git_author_info() -> dict[str, str | None]:
    """
    Retrieves the Git user name and email from the local repository configuration.

    Returns:
        A dictionary with 'name' and 'email' keys. The values will be strings
        if found, otherwise they will be None.
    """
    author_info: dict[str, str | None] = {"name": None, "email": None}

    try:
        # Get the user name
        name_result = subprocess.run(
            ["git", "config", "--get", "user.name"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )  # nosec
        if name_result.returncode == 0:
            author_info["name"] = name_result.stdout.strip() or None

        # Get the user email
        email_result = subprocess.run(
            ["git", "config", "--get", "user.email"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )  # nosec
        if email_result.returncode == 0:
            author_info["email"] = email_result.stdout.strip() or None

    except (FileNotFoundError, subprocess.TimeoutExpired):
        # Handle cases where git is not installed or times out
        return {"name": None, "email": None}

    return author_info


def initialize_git_repo(project_path: Path) -> bool:
    """
    Initialize a git repository in the project directory.

    Returns:
        bool: True if git initialization was successful, False otherwise.

    Bandit:
        This function uses subprocess to run git commands, which is generally safe
        as long as the entry point is the CLI command and the project_path is controlled.
    """
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)  # nosec

        subprocess.run(["git", "init"], cwd=project_path, check=True, capture_output=True)  # nosec

        subprocess.run(["git", "add", "."], cwd=project_path, check=True, capture_output=True)  # nosec

        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=project_path, check=True, capture_output=True)  # nosec

        return True

    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
