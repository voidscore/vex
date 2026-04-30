import json
import logging

from pathlib import Path
from importlib import resources
from datetime import datetime, timezone

from .commit_message import CommitMessageValidator, CommitBump
from .git_repository import GitRepository
from .templates.c_header import TEMPLATE_C_VERSION_HEADER
from .errors import (
    VexError
)


class VexApplication:
    def __init__(self, root: Path):
        self.root_dir = root
        self.vex_dir = self.root_dir / ".vex"
        self.state_file = self.vex_dir / "state.json"
        self.version_file = self.root_dir / "version.json"
        self.logger = logging.getLogger("vex")

    def init_project(self, force: bool = False):
        if self._is_initialized() and not force:
            raise VexError(
                f"already initialized, you can use '--force'"
            )
        
        self._init_env(force=force)
        self._sync_git_integration(force=force)

        self.logger.info(f"initialized in {self.root_dir}")

    def init_project_with_git(self, force: bool = False) -> None:
        self.logger.info("initializing project with git in %s", self.root_dir.resolve())

        git = GitRepository(self.root_dir)

        already_vex_initialized = self._is_initialized()
        already_git_initialized = git.is_initialized()

        if already_vex_initialized and already_git_initialized and not force:
            raise VexError(
                "already initialized, you can use '--force'"
            )

        if not already_git_initialized:
            self.logger.info("initializing git repository")
            git.init()
        else:
            self.logger.info("git repository already exists")

        self._init_env(force=force)
        self._sync_git_integration(force=force)

        git.add(self.root_dir / ".gitignore")
        git.add(self.version_file)

        if git.has_staged_changes():
            self.logger.info("creating initial commit")
            git.commit("chore: initial commit")
        else:
            self.logger.info("nothing to commit for initial commit")

        info = git.get_info()

        if info.branch != "dev":
            self.logger.info("creating and switching to dev branch")
            git.checkout_new_branch("dev")

        self._sync_git_integration(force=force)

        self.logger.info("project initialized with git")

    def sync_build(self):
        if not self._is_initialized():
            raise VexError("is not initialized, you should use 'init'")

        self._sync_git_integration()

        state = self._get_state()
        state["build"] = {
            "count": state["build"]["count"] + 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._update_state(state)

        self._generate_version_from_template()

        self.logger.info(f"command 'sync --build' complete")

    def sync_git_commit_msg(self, message_file: Path) -> None:
        if not self._is_initialized():
            raise VexError("is not initialized, you should use 'init'")

        self._sync_git_integration()
        result = CommitMessageValidator().validate_file(str(message_file))

        if not result.valid:
            raise VexError(result.error or "invalid commit message")
        
        self.logger.info(f"command 'sync --git-commit-msg' complete")

    def sync_git_post_merge(self) -> None:
        if not self._is_initialized():
            raise VexError("is not initialized, you should use 'init'")
        
        # Синхронизируем git-интеграцию:
        # - проверяем наличие git;
        # - проверяем, является ли проект git-репозиторием;
        # - устанавливаем hooks;
        # - обновляем git-секцию в .vex/state.json.
        self._sync_git_integration()

        git = GitRepository(self.root_dir)

        # Если git не установлен или проект не является git-репозиторием,
        # post-merge логика неприменима.
        if not git.is_installed() or not git.is_initialized():
            return

        # Получаем текущее состояние git:
        info = git.get_info()

        # Version bump разрешён только при merge в main.
        # Merge в feature/develop/etc не должен менять version.json.
        if info.branch != "main":
            return

        # HEAD@{1} — положение HEAD до последней операции,
        # HEAD     — текущее положение HEAD после merge.
        #
        # Диапазон HEAD@{1}..HEAD позволяет понять,
        # какие коммиты были добавлены последним merge.
        old_head = git.rev_parse("HEAD@{1}")
        new_head = git.rev_parse("HEAD")

        # Защита от странной ситуации, когда HEAD не изменился.
        # Например, merge ничего не добавил.
        if old_head == new_head:
            return

        # Формируем git range:
        # старое состояние main .. новое состояние main.
        commit_range = f"{old_head}..{new_head}"

        # Получаем только заголовки commit message из этого диапазона.
        # Например:
        #   feat: add api
        #   fix: correct parser
        #   docs: update readme
        subjects = git.log_subjects(commit_range)

        # Анализируем commit messages и выбираем максимальный bump:
        #   feat! -> major
        #   feat  -> minor
        #   fix/perf/refactor -> patch
        #   docs/chore/etc -> none
        bump = self._detect_bump_from_subjects(subjects)

        # Если среди новых коммитов нет ничего, что влияет на версию,
        # version.json не трогаем.
        if bump == CommitBump.NONE:
            return

        # Рассчитываем новую версию на основе текущего version.json.
        new_version = self._bump_version(bump)

        # Записываем новую версию в version.json.
        self._update_version(new_version)

        # Перегенерируем generated/version.h,
        # чтобы локальное состояние соответствовало новой версии.
        self._generate_version_from_template()

        # Добавляем version.json в index.
        #
        # generated/version.h сейчас находится в .gitignore,
        # поэтому его не добавляем.
        git.add(self.version_file)

        # Если после git add действительно есть staged changes,
        # создаём отдельный commit версии.
        #
        # Это важно: hook не должен оставлять version.json
        # просто изменённым в рабочей директории.
        if git.has_staged_changes():
            version_text = self._format_version(new_version)
            git.commit(f"chore(version): bump to {version_text}")

        # После автоматического commit hash изменился.
        # Поэтому ещё раз обновляем .vex/state.json,
        # чтобы там был актуальный git hash/short_hash/dirty.
        self._sync_git_integration()

        self.logger.info(f"command 'sync --git-post-merge' complete")

    def _is_initialized(self) -> bool:
        return (
            self.vex_dir.is_dir() and
            self.state_file.is_file()
        )
    
    def _init_env(self, force: bool):
        self.vex_dir.mkdir(exist_ok=True)
        
        self._update_state(self._default_state())

        if not self.version_file.is_file():
            self._update_version(self._default_version())
        else:
            version = self._get_version()
            self._validate_version(version)

    def _default_state(self) -> dict:
        return {
            "build": {
                "count": 0,
                "timestamp": "",
            },
            "git": {
                "enabled": False,
                "branch": "",
                "hash": "",
                "short_hash": "",
                "commit_count": 0,
                "dirty": False
            }
        }
    
    def _get_state(self) -> dict:
        with open(self.state_file, mode="r", encoding="utf-8") as file:
            return json.load(file)
    
    def _update_state(self, content: dict):
        with open(self.state_file, mode="w", encoding="utf-8") as file:
            json.dump(content, file, indent=4)
            file.write("\n")

    def _default_version(self) -> dict:
        return {
            "version": {
                "major": 1,
                "minor": 0,
                "patch": 0,
            }
        }
    
    def _get_version(self) -> dict:
        with open(self.version_file, mode="r", encoding="utf-8") as file:
            return json.load(file)
        
    def _update_version(self, content: dict):
        self._validate_version(content)

        with open(self.version_file, mode="w", encoding="utf-8") as file:
            json.dump(content, file, indent=4)
            file.write("\n")

    def _validate_version(self, content: dict) -> None:
        if not isinstance(content, dict):
            raise VexError("version.json must contain a JSON object")

        version = content.get("version")
        if not isinstance(version, dict):
            raise VexError("version.json must contain object field: version")

        for key in ("major", "minor", "patch"):
            value = version.get(key)

            if not isinstance(value, int):
                raise VexError(f"version.json field version.{key} must be an integer")

            if value < 0:
                raise VexError(f"version.json field version.{key} must be >= 0")
            
    def _sync_git_integration(self, force: bool = False) -> None:
        git = GitRepository(self.root_dir)

        if not git.is_installed():
            state = self._get_state()
            state["git"]["enabled"] = False
            self._update_state(state)
            return

        if not git.is_initialized():
            state = self._get_state()
            state["git"]["enabled"] = False
            self._update_state(state)
            return
        
        self._ensure_git_config(git)

        git.update_gitignore([
            ".vex/state.json",
            "generated/version.h",
        ])

        git.install_hooks(
            hooks=self._get_embedded_git_hooks(),
            force=force,
        )

        info = git.get_info()

        state = self._get_state()
        state["git"] = {
            "enabled": True,
            "branch": info.branch,
            "hash": info.commit_hash,
            "short_hash": info.short_hash,
            "commit_count": info.commit_count,
            "dirty": info.is_dirty,
        }
        self._update_state(state)

    def _ensure_git_config(self, git: GitRepository) -> None:
        """
        Метод обеспечивает нужную политику merge/pull для проекта.

        Необходимо:
        - гарантировать наличие merge commit (через --no-ff),
        чтобы можно было стабильно отслеживать изменения для version bump;
        - избежать неожиданных merge при git pull.
        """

        # Читаем текущую настройку:
        # merge.ff отвечает за поведение git merge
        # значения:
        #   true  -> fast-forward если возможно (по умолчанию)
        #   false -> всегда создавать merge commit (как --no-ff)
        #   only  -> разрешать только fast-forward
        merge_ff = git.config_get("merge.ff")

        # Если не установлено в "false", принудительно включаем режим --no-ff.
        # Это гарантирует, что даже обычный git merge feature
        # создаст отдельный merge commit.
        #
        # Это важно для vex, потому что:
        # - появляется явная точка merge;
        # - проще анализировать историю;
        # - стабильнее работает version bump.
        if merge_ff != "false":
            git.config_set("merge.ff", "false")

        # Читаем настройку pull.ff:
        # она влияет на поведение git pull
        #
        # значения:
        #   true  -> может сделать merge
        #   false -> всегда merge commit
        #   only  -> только fast-forward (иначе ошибка)
        pull_ff = git.config_get("pull.ff")

        # Устанавливаем pull.ff=only:
        #
        # Это означает:
        # - git pull НЕ будет создавать merge commit;
        # - если fast-forward невозможен — будет ошибка.
        #
        # Зачем это нужно:
        # - избегаем "скрытых" merge-коммитов от pull;
        # - вся логика merge сосредоточена в явных git merge,
        #   где работает vex;
        # - история становится предсказуемой.
        if pull_ff != "only":
            git.config_set("pull.ff", "only")

    def _get_embedded_git_hooks(self) -> dict[str, str]:
        package = "vex.resources.git_hooks"
        hooks: dict[str, str] = {}

        for entry in resources.files(package).iterdir():
            if entry.is_file():
                hooks[entry.name] = entry.read_text(encoding="utf-8")

        return hooks

    def _generate_version_from_template(self) -> None:
        target = self.root_dir / "generated" / "version.h"
        target.parent.mkdir(parents=True, exist_ok=True)

        version = self._get_version()
        self._validate_version(version)

        state = self._get_state()

        version_data = version["version"]
        build_data = state["build"]
        git_data = state["git"]

        content = TEMPLATE_C_VERSION_HEADER.format(
            major=version_data["major"],
            minor=version_data["minor"],
            patch=version_data["patch"],
            build_count=build_data["count"],
            build_time=build_data["timestamp"],
            branch=git_data["branch"],
            hash=git_data["short_hash"],
            dirty=1 if git_data["dirty"] else 0,
        )

        target.write_text(content, encoding="utf-8")
        
    def _detect_bump_from_subjects(self, subjects: list[str]) -> CommitBump:
        validator = CommitMessageValidator()

        result_bump = CommitBump.NONE

        for subject in subjects:
            result = validator.validate(subject)

            if not result.valid:
                continue

            result_bump = self._max_bump(result_bump, result.bump)

        return result_bump

    def _max_bump(self, left: CommitBump, right: CommitBump) -> CommitBump:
        priority = {
            CommitBump.NONE: 0,
            CommitBump.PATCH: 1,
            CommitBump.MINOR: 2,
            CommitBump.MAJOR: 3,
        }

        return left if priority[left] >= priority[right] else right
    
    def _bump_version(self, bump: CommitBump) -> dict:
        version = self._get_version()
        self._validate_version(version)

        data = version["version"]

        major = data["major"]
        minor = data["minor"]
        patch = data["patch"]

        if bump == CommitBump.MAJOR:
            major += 1
            minor = 0
            patch = 0
        elif bump == CommitBump.MINOR:
            minor += 1
            patch = 0
        elif bump == CommitBump.PATCH:
            patch += 1
        else:
            return version

        return {
            "version": {
                "major": major,
                "minor": minor,
                "patch": patch,
            }
        }

    def _format_version(self, version: dict) -> str:
        self._validate_version(version)

        data = version["version"]

        return f"{data['major']}.{data['minor']}.{data['patch']}"