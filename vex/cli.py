import argparse
import sys
import logging
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .app import VexApplication


class LoggerFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[36m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[41m",
    }
    RESET = "\033[0m"

    def format(self, record):
        original = record.levelname
        try:
            color = self.COLORS.get(record.levelno, "")
            record.levelname = f"{color}{original}{self.RESET}".lower()
            return super().format(record)
        finally:
            record.levelname = original


def get_app_version() -> str:
    try:
        return version("vex")
    except PackageNotFoundError:
        return "dev"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vex",
        description="Version generator for make/cmake projects",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"vex {get_app_version()}",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    add_init_parser(subparsers)
    add_sync_parser(subparsers)
    add_doctor_parser(subparsers)
    add_version_parser(subparsers)

    return parser


def add_init_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "init",
        help="Initialize vex in the current project",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing vex files",
    )

    parser.set_defaults(handler=handle_init)


def add_sync_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "sync",
        help="Synchronize vex state and generated version files",
    )

    group = parser.add_mutually_exclusive_group()

    group.add_argument(
        "--build",
        action="store_true",
        help="Sync before project build",
    )

    group.add_argument(
        "--git-commit-msg",
        metavar="MESSAGE_FILE",
        type=Path,
        help="Validate git commit message file",
    )

    group.add_argument(
        "--git-post-merge",
        action="store_true",
        help="Sync after git merge",
    )

    group.add_argument(
        "--manual",
        action="store_true",
        help="Run manual synchronization",
    )

    parser.set_defaults(handler=handle_sync)


def add_doctor_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "doctor",
        help="Check vex project configuration",
    )

    parser.set_defaults(handler=handle_doctor)


def add_version_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "version",
        help="Show project version",
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="Show full version information",
    )

    parser.set_defaults(handler=handle_project_version)


def handle_init(args: argparse.Namespace) -> int:
    app = VexApplication(Path.cwd())
    app.init_project(force=args.force)

    return 0


def handle_sync(args: argparse.Namespace) -> int:
    app = VexApplication(Path.cwd())

    if args.build:
        app.sync_build()
        return 0

    if args.git_commit_msg is not None:
        app.sync_git_commit_msg(args.git_commit_msg)
        return 0

    if args.git_post_merge:
        app.sync_git_post_merge()
        return 0

    # Default mode for `vex sync`
    app.sync_project(source="manual")
    return 0


def handle_doctor(args: argparse.Namespace) -> int:
    app = VexApplication(Path.cwd())
    app.doctor()
    return 0


def handle_project_version(args: argparse.Namespace) -> int:
    app = VexApplication(Path.cwd())

    if args.full:
        print(app.get_full_version())
    else:
        print(app.get_version())

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    level = logging.DEBUG if args.verbose else logging.INFO

    handler = logging.StreamHandler()
    handler.setFormatter(
        LoggerFormatter("vex [%(levelname)s]: %(message)s")
    )

    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
        handlers=[handler]
    )

    logger = logging.getLogger("vex")

    try:
        return args.handler(args)
    except KeyboardInterrupt:
        logger.warning("Interrupted")
        return 130
    except Exception as e:
        logger.error(e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())