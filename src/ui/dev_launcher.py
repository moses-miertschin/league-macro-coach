"""Optional development convenience: launches `python -m src.draft.cli
--watch` and `python -m src.ui.app` together as two subprocesses, so a
developer doesn't need two separate terminals to see the whole pipeline
running end to end while working on this project. Not part of the
shipped application's normal entry point (src/ui/app.py) -- both
processes it launches are exactly what a developer could already run by
hand; this only saves opening a second terminal.

build_watch_command()/build_app_command()/build_arg_parser()/
resolve_app_args() are the directly-testable building blocks; main()
spawns two real subprocesses (one a real Qt window) and blocks, so it's
deliberately untested-by-design, same as src/draft/cli.py's and
src/ui/app.py's own main() functions.

Run with: python -m src.ui.dev_launcher [--interval SECONDS] [-- <args forwarded to src.ui.app, e.g. --demo>]
"""

import argparse
import subprocess
import sys


def build_watch_command(python_executable: str = sys.executable, interval: float | None = None) -> list:
    command = [python_executable, "-m", "src.draft.cli", "--watch"]
    if interval is not None:
        command += ["--interval", str(interval)]
    return command


def build_app_command(python_executable: str = sys.executable, extra_args: list | None = None) -> list:
    command = [python_executable, "-m", "src.ui.app"]
    if extra_args:
        command += list(extra_args)
    return command


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Launch src/draft/cli.py --watch and src/ui/app.py together for local development.",
    )
    parser.add_argument(
        "--interval", type=float, default=None,
        help="Polling interval in seconds for the draft CLI watcher (default: src/draft/cli.py's own default).",
    )
    parser.add_argument(
        "app_args", nargs=argparse.REMAINDER,
        help="Everything after `--` is forwarded to `python -m src.ui.app` (e.g. -- --demo --verbose).",
    )
    return parser


def resolve_app_args(args: argparse.Namespace) -> list:
    """argparse.REMAINDER keeps a leading `--` separator in the captured
    list; this strips it so callers get a clean argv to forward."""
    if args.app_args and args.app_args[0] == "--":
        return args.app_args[1:]
    return list(args.app_args)


def main(argv: list | None = None) -> int:
    args = build_arg_parser().parse_args(argv if argv is not None else sys.argv[1:])

    watch_process = subprocess.Popen(build_watch_command(interval=args.interval))
    try:
        app_result = subprocess.run(build_app_command(extra_args=resolve_app_args(args)))
        return app_result.returncode
    finally:
        watch_process.terminate()
        try:
            watch_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            watch_process.kill()


if __name__ == "__main__":
    sys.exit(main())
