"""Runnable draft command -- the first way to use the draft assistant
without any UI. Wires a real LCUClient into DraftRuntimeService
(src/draft/service.py) and publish_state() (src/runtime/state_publisher.py)
behind a thin argparse CLI, following the same "argparse in main(), plain
injectable functions underneath" shape src/history/backfill.py already
established.

Two modes:
    --once   one poll, publish, print a status line, exit.
    --watch  poll repeatedly until Ctrl+C.

--watch deliberately drives DraftRuntimeService.poll_once() itself in a
plain loop (poll, publish, sleep, repeat) rather than spinning up
SessionPoller's own background thread -- this CLI's whole job while
running is to watch, so there's no second thread of work competing for
the main thread the way SessionPoller's design anticipates for a future
UI. This still reuses "the same poll_once foundation" the task allows
instead of reimplementing a second polling architecture: the loop body is
the same trivial "call it, sleep, repeat" shape SessionPoller's own
_run_loop() uses internally, not a new implementation of retry/backoff/
idle-tracking logic. The sleep between polls (never zero) is what keeps
this from busy-looping, and it's injectable so tests never need a real
wait or a real Ctrl+C.

No web server, no GUI framework, no paid service -- coordinates only
already-built pieces.
"""

import argparse
import json
import time
from pathlib import Path

from src.draft.client import LCUClient
from src.draft.service import DraftRuntimeService
from src.runtime.state_publisher import DEFAULT_OUTPUT_PATH, publish_state

DEFAULT_INTERVAL_SECONDS = 5.0
MAX_RECOMMENDATIONS_SHOWN = 3


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Poll the League client for champ-select draft state and publish it locally."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Perform a single poll, publish the result, and exit.")
    mode.add_argument("--watch", action="store_true", help="Poll repeatedly on --interval until Ctrl+C.")
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT_PATH,
        help=f"Where to write the published state JSON (default: {DEFAULT_OUTPUT_PATH}).",
    )
    parser.add_argument(
        "--interval", type=float, default=DEFAULT_INTERVAL_SECONDS,
        help=f"Polling interval in seconds for --watch (default: {DEFAULT_INTERVAL_SECONDS}).",
    )
    parser.add_argument(
        "--lockfile", type=Path, default=None,
        help="Path to the League client's lockfile (default: the standard install location).",
    )
    parser.add_argument("--verbose", action="store_true", help="Also print the full published state after each poll.")
    return parser


def _build_service(lockfile_path: Path | None) -> DraftRuntimeService:
    lcu_client = LCUClient(lockfile_path=lockfile_path) if lockfile_path is not None else LCUClient()
    return DraftRuntimeService(session_source=lcu_client, client_running_check=lcu_client.is_client_running)


def _format_status(state: dict, output_path: Path, verbose: bool) -> str:
    lines = [f"[draft] state={state['state']}  ->  {output_path}"]
    if state.get("error"):
        lines.append(f"  error: {state['error']}")
    recommendations = state.get("recommendations") or []
    if recommendations:
        lines.append(f"  {len(recommendations)} recommendation(s):")
        for rec in recommendations[:MAX_RECOMMENDATIONS_SHOWN]:
            lines.append(f"    - [{rec.get('severity')}] {rec.get('category')}: {rec.get('subject')}")
        if len(recommendations) > MAX_RECOMMENDATIONS_SHOWN:
            lines.append(f"    ... and {len(recommendations) - MAX_RECOMMENDATIONS_SHOWN} more")
    if verbose:
        lines.append(json.dumps(state, indent=2, sort_keys=True))
    return "\n".join(lines)


def run_once(
    service: DraftRuntimeService,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    publisher_fn=publish_state,
    print_fn=print,
    verbose: bool = False,
) -> dict:
    state = service.poll_once()
    publisher_fn(state, output_path=output_path)
    print_fn(_format_status(state, output_path, verbose))
    return state


def run_watch(
    service: DraftRuntimeService,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    publisher_fn=publish_state,
    print_fn=print,
    verbose: bool = False,
    sleep_fn=time.sleep,
) -> None:
    print_fn(f"[draft] watching every {interval_seconds}s, publishing to {output_path} (Ctrl+C to stop)")
    try:
        while True:
            state = service.poll_once()
            publisher_fn(state, output_path=output_path)
            print_fn(_format_status(state, output_path, verbose))
            sleep_fn(interval_seconds)
    except KeyboardInterrupt:
        print_fn("[draft] stopping (Ctrl+C received).")


def main(argv=None) -> None:
    args = build_arg_parser().parse_args(argv)
    service = _build_service(args.lockfile)

    if args.once:
        run_once(service, output_path=args.output, verbose=args.verbose)
    else:
        run_watch(service, output_path=args.output, interval_seconds=args.interval, verbose=args.verbose)


if __name__ == "__main__":
    main()
