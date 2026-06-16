#!/usr/bin/env python3
"""Minimal per-conversation flow state helper for one-shot skills."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def detect_context() -> tuple[str | None, str | None, str | None]:
    claude_code_session_id = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if claude_code_session_id:
        return "claude", claude_code_session_id, "CLAUDE_CODE_SESSION_ID"

    claude_session_id = os.environ.get("CLAUDE_SESSION_ID")
    if claude_session_id:
        return "claude", claude_session_id, "CLAUDE_SESSION_ID"

    codex_thread_id = os.environ.get("CODEX_THREAD_ID")
    if codex_thread_id:
        return "codex", codex_thread_id, "CODEX_THREAD_ID"

    return None, None, None


def default_state_root() -> Path:
    configured = os.environ.get("ONE_SHOT_STATE_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".one-shot" / "flow-state"


def state_path(state_root: Path, flow: str, conversation_id: str) -> Path:
    safe_flow = "".join(
        char if char.isalnum() or char in ("-", "_", ".") else "_"
        for char in flow
    )
    safe_id = "".join(
        char if char.isalnum() or char in ("-", "_", ".") else "_"
        for char in conversation_id
    )
    return state_root / safe_flow / f"{safe_id}.json"


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_state(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def build_initial_state(args: argparse.Namespace, tool: str, conversation_id: str) -> dict:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "tool": tool,
        "conversation_id": conversation_id,
        "flow": args.flow,
        "mode": args.mode,
        "stage": args.stage,
        "status": args.status,
        "last_completed_stage": args.last_completed_stage,
        "allowed_next": args.allowed_next,
        "blocked_next": args.blocked_next,
        "cwd": str(Path.cwd()),
        "updated_at": now,
    }


def apply_state_args(state: dict, args: argparse.Namespace) -> dict:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    state["flow"] = args.flow
    state["mode"] = args.mode
    state["stage"] = args.stage
    state["status"] = args.status
    state["last_completed_stage"] = args.last_completed_stage
    state["allowed_next"] = args.allowed_next
    state["blocked_next"] = args.blocked_next
    state["cwd"] = str(Path.cwd())
    state["updated_at"] = now
    return state


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resolve and optionally initialize one-shot per-conversation state."
    )
    parser.add_argument("command", choices=("resolve", "init", "show", "update"))
    parser.add_argument("--state-root", default=None)
    parser.add_argument("--flow", default="one-shot")
    parser.add_argument("--mode", default="auto")
    parser.add_argument("--stage", default="brainstorm")
    parser.add_argument("--status", default="in_progress")
    parser.add_argument("--last-completed-stage", default=None)
    parser.add_argument("--allowed-next", nargs="*", default=["confirm"])
    parser.add_argument(
        "--blocked-next",
        nargs="*",
        default=["plan", "execute", "finish"],
    )
    args = parser.parse_args()

    tool, conversation_id, source = detect_context()
    if not tool or not conversation_id:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": "missing_conversation_id",
                    "message": "未找到 CLAUDE_CODE_SESSION_ID、CLAUDE_SESSION_ID 或 CODEX_THREAD_ID，不能安全恢复阶段。",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    state_root = Path(args.state_root).expanduser() if args.state_root else default_state_root()
    path = state_path(state_root, args.flow, conversation_id)
    result = {
        "ok": True,
        "tool": tool,
        "conversation_id": conversation_id,
        "id_source": source,
        "state_root": str(state_root),
        "state_path": str(path),
    }

    if args.command == "resolve":
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "init":
        state = load_state(path)
        created = not bool(state)
        if not state:
            state = build_initial_state(args, tool, conversation_id)
            write_state(path, state)
        result["state"] = state
        result["created"] = created
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.command == "update":
        state = load_state(path)
        if not state:
            state = build_initial_state(args, tool, conversation_id)
        else:
            state = apply_state_args(state, args)
        write_state(path, state)
        result["state"] = state
        result["updated"] = True
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    result["state"] = load_state(path)
    result["exists"] = path.exists()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
