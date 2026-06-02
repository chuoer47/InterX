#!/usr/bin/env python3
"""CLI tool for multi-turn conversation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chat.pipeline import chat, get_session, reset_session
from chat.config import ChatSettings


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-turn chat over product manuals.")
    sub = parser.add_subparsers(dest="command")

    # chat command
    chat_p = sub.add_parser("send", help="Send a message in a conversation.")
    chat_p.add_argument("message", help="User message.")
    chat_p.add_argument("--session", default=None, help="Session ID (auto-created if omitted).")
    chat_p.add_argument("--config", default=None, help="Config YAML path.")
    chat_p.add_argument("--json", action="store_true", help="Output JSON.")

    # history command
    hist_p = sub.add_parser("history", help="Show session history.")
    hist_p.add_argument("session_id", help="Session ID.")
    hist_p.add_argument("--config", default=None)

    # reset command
    reset_p = sub.add_parser("reset", help="Reset a session.")
    reset_p.add_argument("session_id", help="Session ID.")
    reset_p.add_argument("--config", default=None)

    args = parser.parse_args()

    if args.command == "send":
        settings = ChatSettings.load(args.config)
        result = chat(args.message, session_id=args.session, settings=settings)
        if args.json:
            print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        else:
            print(f"Session: {result.session_id}")
            if result.history_turns_used > 0:
                print(f"History: {result.history_turns_used} turns used"
                      f"{' (with summary)' if result.summary_used else ''}")
            if result.rewritten_query != result.user_message:
                print(f"Rewritten: {result.rewritten_query}")
            print(f"\n{result.assistant_message}")

    elif args.command == "history":
        settings = ChatSettings.load(args.config)
        session = get_session(args.session_id, settings=settings)
        if not session:
            print(f"Session not found: {args.session_id}")
            sys.exit(1)
        print(f"Session: {session.session_id}")
        print(f"Turns: {session.turn_count}")
        if session.summary:
            print(f"Summary: {session.summary}")
        for t in session.turns:
            print(f"\n[{t.turn_id}] {t.timestamp}")
            print(f"  Q: {t.user_message}")
            print(f"  A: {t.assistant_message[:200]}...")

    elif args.command == "reset":
        settings = ChatSettings.load(args.config)
        session = reset_session(args.session_id, settings=settings)
        print(f"Session reset: {session.session_id}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
