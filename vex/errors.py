from __future__ import annotations


class VexError(Exception):
    """Base exception for all vex-related errors."""
    pass


class GitError(VexError):
    pass


class GitNotInstalledError(GitError):
    pass


class GitRepositoryError(GitError):
    pass


class GitCommandError(GitError):
    def __init__(self, command: list[str], returncode: int, stderr: str):
        self.command = command
        self.returncode = returncode
        self.stderr = stderr

        super().__init__(
            f"git command failed: {' '.join(command)} "
            f"(exit code {returncode}): {stderr.strip()}"
        )