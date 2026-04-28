import re
from dataclasses import dataclass
from enum import Enum


class CommitBump(str, Enum):
    NONE = "none"
    PATCH = "patch"
    MINOR = "minor"
    MAJOR = "major"


@dataclass(frozen=True)
class CommitMessageResult:
    valid: bool
    bump: CommitBump
    subject: str
    error: str | None = None


class CommitMessageValidator:
    _PATTERN = re.compile(
        r"^(?P<type>[a-z]+)"
        r"(?:\((?P<scope>[a-zA-Z0-9_\-./]+)\))?"
        r"(?P<breaking>!)?"
        r": "
        r"(?P<description>.+)$"
    )

    _ALLOWED_TYPES = {
        "feat",
        "fix",
        "perf",
        "refactor",
        "docs",
        "test",
        "build",
        "ci",
        "chore",
        "style",
        "revert",
    }

    _PATCH_TYPES = {
        "fix",
        "perf",
        "refactor",
    }

    _MINOR_TYPES = {
        "feat",
    }

    def validate(self, message: str) -> CommitMessageResult:
        subject = self._extract_subject(message)

        if not subject:
            return CommitMessageResult(
                valid=False,
                bump=CommitBump.NONE,
                subject="",
                error="empty commit message",
            )

        if self._is_allowed_git_message(subject):
            return CommitMessageResult(
                valid=True,
                bump=CommitBump.NONE,
                subject=subject,
            )

        match = self._PATTERN.match(subject)
        if not match:
            return CommitMessageResult(
                valid=False,
                bump=CommitBump.NONE,
                subject=subject,
                error="commit message must follow Conventional Commits format",
            )

        commit_type = match.group("type")
        breaking = match.group("breaking") == "!"

        if commit_type not in self._ALLOWED_TYPES:
            return CommitMessageResult(
                valid=False,
                bump=CommitBump.NONE,
                subject=subject,
                error=f"unsupported commit type: {commit_type}",
            )

        if breaking and commit_type != "feat":
            return CommitMessageResult(
                valid=False,
                bump=CommitBump.NONE,
                subject=subject,
                error="breaking marker '!' is allowed only for feat! commits",
            )

        bump = self._detect_bump(
            commit_type=commit_type,
            breaking=breaking,
        )

        return CommitMessageResult(
            valid=True,
            bump=bump,
            subject=subject,
        )

    def validate_file(self, path: str) -> CommitMessageResult:
        with open(path, "r", encoding="utf-8") as file:
            return self.validate(file.read())

    def _extract_subject(self, message: str) -> str:
        for line in message.splitlines():
            line = line.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            return line

        return ""

    def _detect_bump(
        self,
        commit_type: str,
        breaking: bool,
    ) -> CommitBump:
        if commit_type == "feat" and breaking:
            return CommitBump.MAJOR

        if commit_type in self._MINOR_TYPES:
            return CommitBump.MINOR

        if commit_type in self._PATCH_TYPES:
            return CommitBump.PATCH

        return CommitBump.NONE

    def _is_allowed_git_message(self, subject: str) -> bool:
        return (
            subject.startswith("Merge ")
            or subject.startswith("Revert ")
        )