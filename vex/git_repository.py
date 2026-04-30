from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .errors import (
    GitCommandError,
    GitNotInstalledError,
    GitRepositoryError,
)


@dataclass(frozen=True)
class GitInfo:
    branch: str
    commit_hash: str
    short_hash: str
    commit_count: int
    is_dirty: bool


class GitRepository:
    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()

    def is_installed(self) -> bool:
        return shutil.which("git") is not None

    def ensure_installed(self) -> None:
        if not self.is_installed():
            raise GitNotInstalledError("git is not installed or not found in PATH")

    def is_initialized(self) -> bool:
        if not self.is_installed():
            return False

        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=self.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        return result.returncode == 0 and result.stdout.strip() == "true"

    def ensure_initialized(self) -> None:
        if not self.is_initialized():
            raise GitRepositoryError(f"{self.root} is not a git repository")

    def get_git_dir(self) -> Path:
        self.ensure_initialized()
        return self.root / self._exec("rev-parse", "--git-dir").strip()

    def get_hooks_dir(self) -> Path:
        self.ensure_initialized()
        return self.root / self._exec("rev-parse", "--git-path", "hooks").strip()

    def config_get(self, key: str) -> str | None:
        self.ensure_initialized()

        try:
            value = self._exec("config", "--local", "--get", key).strip()
        except GitCommandError:
            return None

        return value or None

    def config_set(self, key: str, value: str) -> None:
        self.ensure_initialized()
        self._exec("config", "--local", key, value)

    def update_gitignore(self, names: Iterable[str]) -> None:
        self.ensure_initialized()

        gitignore_path = self.root / ".gitignore"
        existing_lines: list[str] = []

        if gitignore_path.exists():
            existing_lines = gitignore_path.read_text(encoding="utf-8").splitlines()

        existing_entries = {
            line.strip()
            for line in existing_lines
            if line.strip() and not line.strip().startswith("#")
        }

        new_entries: list[str] = []

        for name in names:
            entry = name.strip()
            if entry and entry not in existing_entries:
                new_entries.append(entry)

        if not new_entries:
            return

        with open(gitignore_path, mode="a", encoding="utf-8") as file:
            if existing_lines and existing_lines[-1].strip():
                file.write("\n")

            file.write("\n# vex\n")
            for entry in new_entries:
                file.write(f"{entry}\n")

    def install_hooks(self, hooks: dict[str, str], force: bool = False) -> None:
        self.ensure_initialized()

        hooks_dir = self.get_hooks_dir()
        hooks_dir.mkdir(parents=True, exist_ok=True)

        for hook_name, content in hooks.items():
            target_hook = hooks_dir / hook_name

            if target_hook.exists() and not force:
                continue

            target_hook.write_text(content, encoding="utf-8")
            target_hook.chmod(0o755)

    def has_commits(self) -> bool:
        self.ensure_initialized()

        result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD"],
            cwd=self.root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        return result.returncode == 0

    def get_info(self) -> GitInfo:
        self.ensure_installed()
        self.ensure_initialized()

        branch = self._get_branch()

        if not self.has_commits():
            return GitInfo(
                branch=branch,
                commit_hash="",
                short_hash="",
                commit_count=0,
                is_dirty=False,
            )

        commit_hash = self._exec("rev-parse", "HEAD").strip()
        short_hash = self._exec("rev-parse", "--short", "HEAD").strip()
        commit_count = int(self._exec("rev-list", "--count", "HEAD").strip())
        is_dirty = bool(self._exec("status", "--porcelain").strip())

        return GitInfo(
            branch=branch,
            commit_hash=commit_hash,
            short_hash=short_hash,
            commit_count=commit_count,
            is_dirty=is_dirty,
        )
    
    def init(self) -> None:
        self.ensure_installed()
        self._exec("init")

    def checkout_new_branch(self, branch: str) -> None:
        self.ensure_initialized()
        self._exec("checkout", "-b", branch)

    def add(self, path: Path | str) -> None:
        self.ensure_initialized()
        self._exec("add", self._normalize_path(path))

    def commit(self, message: str) -> None:
        self.ensure_initialized()
        self._exec("commit", "-m", message)

    def has_staged_changes(self) -> bool:
        self.ensure_initialized()
        return bool(self._exec("diff", "--cached", "--name-only").strip())
    
    def rev_parse(self, ref: str) -> str:
        self.ensure_initialized()
        return self._exec("rev-parse", ref).strip()

    def log_subjects(self, commit_range: str) -> list[str]:
        self.ensure_initialized()

        output = self._exec(
            "log",
            "--format=%s",
            commit_range,
        ).strip()

        if not output:
            return []

        return output.splitlines()

    def _get_branch(self) -> str:
        try:
            return self._exec("symbolic-ref", "--short", "HEAD").strip()
        except GitCommandError:
            return self._exec("rev-parse", "--abbrev-ref", "HEAD").strip()

    def _normalize_path(self, path: Path | str) -> str:
        resolved = Path(path)

        if not resolved.is_absolute():
            return str(resolved)

        try:
            return str(resolved.resolve().relative_to(self.root))
        except ValueError:
            return str(resolved)

    def _exec(self, *args: str) -> str:
        self.ensure_installed()

        command = ["git", *args]

        result = subprocess.run(
            command,
            cwd=self.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if result.returncode != 0:
            raise GitCommandError(command, result.returncode, result.stderr)

        return result.stdout