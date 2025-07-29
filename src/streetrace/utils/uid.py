"""Get user's name from GitHub, Git, or OS for session management.

This module provides functionality to retrieve a reliable user identifier
through multiple fallback methods, supporting StreetRace's session tracking
and attribution capabilities.
"""

import getpass
import shutil
import subprocess  # nosec B404 no user input


def get_user_identity() -> str:
    """Get user's id from GitHub, Git, or OS.

    Attempts to identify the user in the following order:
    1. GitHub login via GitHub CLI
    2. Git user.name configuration
    3. OS username as fallback

    Returns:
        A string containing the user identifier from the first successful method

    """
    # 1. Try GitHub CLI (`gh`)
    gh_path = shutil.which("gh")
    if gh_path:
        try:
            from streetrace.log import get_logger
            get_logger(__name__).info("GitHub CLI path: {gh_path}")

            result = subprocess.run( # noqa: S603
                [gh_path, "api", "user", "--jq", ".login"],  # nosec B603 no user input
                capture_output=True,
                text=True,
                check=True,
            )
            login = result.stdout.strip()
            if login:
                return login
        except subprocess.CalledProcessError:
            pass  # gh command failed

    # 2. Try git config user.name
    git_path = shutil.which("git")
    if git_path:
        try:
            from streetrace.log import get_logger
            get_logger(__name__).info(f"Git CLI path: {git_path}")

            result = subprocess.run( # noqa: S603
                [git_path, "config", "user.name"],  # nosec B603 no user input
                capture_output=True,
                text=True,
                check=True,
            )
            username = result.stdout.strip()
            if username:
                return username
        except subprocess.CalledProcessError:
            pass  # git config failed

    # 3. Fallback: OS user
    return getpass.getuser()
