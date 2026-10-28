"""JSON CLI sharing exactly the same workflow as MCP."""
import argparse
import json
from pathlib import Path
import sys
import time

from .project import Toolkit
from .storage import InputError, read_json


def main():
    parser = argparse.ArgumentParser(description="Agent Video Toolkit — local, model-free execution")
    parser.add_argument("--root", type=Path, default=Path("runtime"), help="Dedicated runtime (never share Studio runtime)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("projects")
    p = sub.add_parser("prepare")
    p.add_argument("manifest", type=Path)
    p.add_argument("--visual-brief", required=True)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--preview-width", type=int)
    p.add_argument("--allow-synthetic", action="store_true")
    p = sub.add_parser("task")
    p.add_argument("run_id"); p.add_argument("worker_id"); p.add_argument("--claimant", required=True)
    p = sub.add_parser("submit")
    p.add_argument("run_id"); p.add_argument("worker_id"); p.add_argument("result", type=Path)
    p.add_argument("--claim-token", required=True); p.add_argument("--expected-sha256")
    for command in ("assemble", "render", "status", "_render"):
        p = sub.add_parser(command, help=argparse.SUPPRESS if command == "_render" else command)
        p.add_argument("run_id")
        if command == "render":
            p.add_argument("--wait", action="store_true")
            p.add_argument("--timeout", type=int, default=7200)
    p = sub.add_parser("demo", help="Generate only synthetic inputs, then execute the full pipeline")
    p.add_argument("output", type=Path)
    p.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    try:
        toolkit = Toolkit(args.root)
        if args.command == "prepare":
            result = toolkit.prepare(args.manifest, args.visual_brief, args.workers, args.preview_width, args.allow_synthetic)
        elif args.command == "task":
            result = toolkit.task(args.run_id, args.worker_id, args.claimant)
        elif args.command == "submit":
            result = toolkit.submit(args.run_id, args.worker_id, args.claim_token, read_json(args.result), args.expected_sha256)
        elif args.command == "_render":
            from .renderer import render_run
            render_run(args.root, args.run_id)
            return
        elif args.command == "demo":
            from .demo import demo
            result = demo(toolkit, args.output, args.prepare_only)
        else:
            result = getattr(toolkit, args.command)(*([args.run_id] if hasattr(args, "run_id") else []))
            if args.command == "render" and args.wait:
                result = wait(toolkit, args.run_id, args.timeout)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result.get("state") in ("failed", "interrupted"):
            raise SystemExit(1)
    except (InputError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1) from exc


def wait(toolkit, run_id, timeout=7200):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = toolkit.status(run_id)
        if state["state"] != "rendering":
            return state
        time.sleep(.5)
    raise InputError("Wait timed out; renderer may still run. Query status; do not resubmit.")
