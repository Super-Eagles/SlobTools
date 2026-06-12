
import sys
import os
import argparse
import json

# Fix encoding issues on Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# Setup paths
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from SlobMemory import api
    from SlobMemory import config
except ImportError:
    skills_path = os.path.join(current_dir, "skills")
    sys.path.append(skills_path)
    try:
        try:
            from memory_skill_v3 import api
            from memory_skill_v3 import config
        except ImportError:
            try:
                from memory_skill_v2 import api
                from memory_skill_v2 import config
            except ImportError:
                from memory_system import api
                from memory_system import config
    except ImportError:
        print(f"Error: Could not find memory core")
        sys.exit(1)

if not hasattr(config, 'USER_ID'):
    config.USER_ID = ""
if not hasattr(config, 'SESSION_ID'):
    config.SESSION_ID = ""

def main():
    parser = argparse.ArgumentParser(description="Memory Skill Global CLI")
    subparsers = parser.add_subparsers(dest="command")

    user_required = not bool(config.USER_ID)
    session_required = not bool(config.SESSION_ID)

    # remember: memory remember --user slob --session xxx --text "query"
    rem_parser = subparsers.add_parser("remember")
    rem_parser.add_argument("--user", required=user_required)
    rem_parser.add_argument("--session", required=session_required)
    rem_parser.add_argument("--turn", type=int, default=1)
    rem_parser.add_argument("--text", required=True)

    # memorize: memory memorize --user slob --session xxx --summary "..."
    mem_parser = subparsers.add_parser("memorize")
    mem_parser.add_argument("--user", required=user_required)
    mem_parser.add_argument("--session", required=session_required)
    mem_parser.add_argument("--turn", type=int, default=1)
    mem_parser.add_argument("--summary", required=True)
    mem_parser.add_argument("--keywords", nargs="*", default=[])
    mem_parser.add_argument("--raw_q", default="")
    mem_parser.add_argument("--raw_a", default="")

    # flush: memory flush --user slob --session xxx
    flush_parser = subparsers.add_parser("flush")
    flush_parser.add_argument("--user", required=user_required)
    flush_parser.add_argument("--session", required=session_required)

    # stats: memory stats --user slob
    stats_parser = subparsers.add_parser("stats")
    stats_parser.add_argument("--user", required=user_required)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    # Resolve user and session values
    user = getattr(args, "user", None) or config.USER_ID
    session = getattr(args, "session", None) or config.SESSION_ID

    # Double check presence
    if args.command in ("remember", "memorize", "flush", "stats"):
        if not user:
            print("Error: --user is required (or MEMORY_USER_ID environment variable must be set)", file=sys.stderr)
            sys.exit(1)
    if args.command in ("remember", "memorize", "flush"):
        if not session:
            print("Error: --session is required (or MEMORY_SESSION_ID environment variable must be set)", file=sys.stderr)
            sys.exit(1)

    # Initialize
    api.setup()

    if args.command == "remember":
        result = api.remember(user, session, args.turn, args.text)
        print(result)
    elif args.command == "memorize":
        m_ids = api.memorize(user, session, args.turn, args.summary, args.keywords, args.raw_q, args.raw_a)
        print(f"Memory saved: {m_ids}")
    elif args.command == "flush":
        stats = api.flush(user, session)
        print(f"Session flushed: {stats}")
    elif args.command == "stats":
        print(api.get_stats(user))

if __name__ == "__main__":
    main()
