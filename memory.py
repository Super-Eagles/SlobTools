
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
skills_path = os.path.join(current_dir, "skills")
sys.path.append(skills_path)

try:
    # Try importing from the preferred package name
    try:
        from memory_skill_v2 import api
    except ImportError:
        from memory_system import api
except ImportError:
    print(f"Error: Could not find memory core in {skills_path}")
    sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Memory Skill Global CLI")
    subparsers = parser.add_subparsers(dest="command")

    # remember: memory remember --user slob --session xxx --text "query"
    rem_parser = subparsers.add_parser("remember")
    rem_parser.add_argument("--user", required=True)
    rem_parser.add_argument("--session", required=True)
    rem_parser.add_argument("--turn", type=int, default=1)
    rem_parser.add_argument("--text", required=True)

    # memorize: memory memorize --user slob --session xxx --summary "..."
    mem_parser = subparsers.add_parser("memorize")
    mem_parser.add_argument("--user", required=True)
    mem_parser.add_argument("--session", required=True)
    mem_parser.add_argument("--turn", type=int, default=1)
    mem_parser.add_argument("--summary", required=True)
    mem_parser.add_argument("--keywords", nargs="*", default=[])
    mem_parser.add_argument("--raw_q", default="")
    mem_parser.add_argument("--raw_a", default="")

    # flush: memory flush --user slob --session xxx
    flush_parser = subparsers.add_parser("flush")
    flush_parser.add_argument("--user", required=True)
    flush_parser.add_argument("--session", required=True)

    # stats: memory stats --user slob
    stats_parser = subparsers.add_parser("stats")
    stats_parser.add_argument("--user", required=True)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    # Initialize
    api.setup()

    if args.command == "remember":
        result = api.remember(args.user, args.session, args.turn, args.text)
        print(result)
    elif args.command == "memorize":
        m_ids = api.memorize(args.user, args.session, args.turn, args.summary, args.keywords, args.raw_q, args.raw_a)
        print(f"Memory saved: {m_ids}")
    elif args.command == "flush":
        stats = api.flush(args.user, args.session)
        print(f"Session flushed: {stats}")
    elif args.command == "stats":
        print(api.get_stats(args.user))

if __name__ == "__main__":
    main()
