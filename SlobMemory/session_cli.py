# ── 路径自配置（必须在所有本包导入之前）────────────────────────────────────
import sys as _sys
import os as _os

try:
    from . import api
except ImportError:
    _this_dir = _os.path.dirname(_os.path.abspath(__file__))
    _pkg_name = _os.path.basename(_this_dir)
    _pkg_parent = _os.path.dirname(_this_dir)
    if _pkg_parent not in _sys.path:
        _sys.path.insert(0, _pkg_parent)
    import importlib
    api = importlib.import_module(f"{_pkg_name}.api")

# ── 正常导入 ──────────────────────────────────────────────────────────────────
import argparse
import getpass
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    from filelock import FileLock
    _HAS_FILELOCK = True
except ImportError:
    _HAS_FILELOCK = False

STATE_FILE = Path(__file__).with_name("active_sessions.json")
_LOCK_FILE  = Path(__file__).with_name("active_sessions.lock")


# ── 状态文件工具 ──────────────────────────────────────────────────────────────

def _normalize_workspace(workspace: str) -> str:
    return _os.path.normcase(str(Path(workspace).resolve()))


def _load_state():
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(data):
    # 原子写入：添加 PID 防止并发覆盖，再替换以保证无损
    tmp = STATE_FILE.with_suffix(f".{_os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(STATE_FILE)


def _state_lock():
    """返回文件锁上下文；若 filelock 未安装则降级为无锁（仍可用，并发写入时有小概率覆盖）。"""
    if _HAS_FILELOCK:
        return FileLock(str(_LOCK_FILE), timeout=5)
    import contextlib
    return contextlib.nullcontext()


def _default_user_id():
    return f"codex_{getpass.getuser()}"


def _new_session_id(workspace: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = Path(workspace).name or "workspace"
    safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name)
    return f"{safe_name}_{stamp}"


def _ensure_session(workspace: str, user_id: Optional[str] = None, reset: bool = False, create: bool = True):
    workspace = _normalize_workspace(workspace)
    from . import config

    resolved_user_id = user_id or config.USER_ID or _default_user_id()

    with _state_lock():
        state = _load_state()
        entry = state.get(workspace)

        if reset or entry is None:
            if not create:
                return None
            now = datetime.now().isoformat()
            entry = {
                "workspace":  workspace,
                "user_id":    resolved_user_id,
                "session_id": config.SESSION_ID or _new_session_id(workspace),
                "turn":       1,
                "created_at": now,
                "updated_at": now,
            }
            state[workspace] = entry
            _save_state(state)
            return entry

        has_updates = False
        target_user = user_id or config.USER_ID
        if target_user and entry.get("user_id") != target_user:
            entry["user_id"]    = target_user
            has_updates = True

        if config.SESSION_ID and entry.get("session_id") != config.SESSION_ID:
            entry["session_id"] = config.SESSION_ID
            has_updates = True

        if has_updates:
            entry["updated_at"] = datetime.now().isoformat()
            state[workspace]    = entry
            _save_state(state)

    return entry


def _update_entry(workspace: str, entry):
    workspace = _normalize_workspace(workspace)
    with _state_lock():
        state = _load_state()
        current = state.get(workspace, {})
        current.update(entry)
        current["updated_at"] = datetime.now().isoformat()
        state[workspace] = current
        _save_state(state)


def _remove_entry(workspace: str):
    workspace = _normalize_workspace(workspace)
    with _state_lock():
        state = _load_state()
        if workspace in state:
            del state[workspace]
            _save_state(state)


def _parse_keywords(value: str):
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except Exception:
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]
    if isinstance(parsed, str) and parsed.strip():
        return [parsed.strip()]
    return []


def _read_text_file(path: str):
    target = Path(path)
    last_error = None
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "utf-16-le", "gbk"):
        try:
            return target.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Failed to read file {path} with valid encoding.")


def _pick_text_arg(direct_value, file_value, field_name: str):
    if direct_value not in (None, ""):
        return str(direct_value).lstrip("\ufeff")
    if file_value not in (None, ""):
        return _read_text_file(file_value).lstrip("\ufeff")
    raise SystemExit(f"ERROR: {field_name} is required (use --{field_name.lower()} or --{field_name.lower()}-file)")


def _print_json(payload):
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    try:
        print(text)
    except UnicodeEncodeError:
        print(json.dumps(payload, ensure_ascii=True, indent=2))


def _strip_bom_text(value):
    if isinstance(value, str):
        return value.replace("\ufeff", "")
    return value


# ── 子命令处理函数 ────────────────────────────────────────────────────────────

def cmd_setup(args):
    try:
        api.setup()
        entry = _ensure_session(args.workspace, args.user_id, False)
        _print_json({
            "ok":         True,
            "workspace":  entry["workspace"],
            "user_id":    entry["user_id"],
            "session_id": entry["session_id"],
        })
    except RuntimeError as exc:
        _print_json({"ok": False, "error": str(exc)})
        raise SystemExit(1)


def cmd_ensure(args):
    entry = _ensure_session(args.workspace, args.user_id, args.reset)
    _print_json(entry)


def cmd_show(args):
    entry = _ensure_session(args.workspace, args.user_id, False, create=False)
    if entry is None:
        _print_json({"ok": False, "error": "session_not_found", "workspace": args.workspace})
    else:
        _print_json(entry)


def cmd_remember(args):
    api.setup()
    entry = _ensure_session(args.workspace, args.user_id, False)
    memory_text = api.remember(
        user_id    = entry["user_id"],
        session_id = entry["session_id"],
        turn       = int(entry["turn"]),
        query_text = args.query,
    )
    memory_text = _strip_bom_text(memory_text)
    _print_json({
        "workspace":   entry["workspace"],
        "user_id":     entry["user_id"],
        "session_id":  entry["session_id"],
        "turn":        entry["turn"],
        "memory_text": memory_text,
    })


def cmd_write(args):
    api.setup()
    entry    = _ensure_session(args.workspace, args.user_id, False)
    question = _pick_text_arg(args.question, args.question_file, "question")
    answer   = _pick_text_arg(args.answer,   args.answer_file,   "answer")
    summary  = _pick_text_arg(args.summary,  args.summary_file,  "summary")
    keywords = _parse_keywords(args.keywords_json)
    
    summary_stripped = summary.strip()
    if not summary_stripped or summary_stripped in ("无", "none", "{}", "未提取到结构化摘要", "本轮对话完成，未提取到结构化摘要。"):
        mem_ids = []
    else:
        mem_ids  = api.memorize(
            user_id    = entry["user_id"],
            session_id = entry["session_id"],
            turn       = int(entry["turn"]),
            summary    = summary_stripped,
            keywords   = keywords,
            raw_q      = question,
            raw_a      = answer,
        )
    entry["turn"] = int(entry["turn"]) + 1
    _update_entry(args.workspace, entry)
    _print_json({
        "workspace":  entry["workspace"],
        "user_id":    entry["user_id"],
        "session_id": entry["session_id"],
        "next_turn":  entry["turn"],
        "mem_ids":    mem_ids,
    })


def cmd_flush(args):
    api.setup()
    entry = _ensure_session(args.workspace, args.user_id, False)
    stats = api.flush(
        user_id    = entry["user_id"],
        session_id = entry["session_id"],
    )
    _remove_entry(args.workspace)
    _print_json({
        "workspace":  entry["workspace"],
        "user_id":    entry["user_id"],
        "session_id": entry["session_id"],
        "flushed":    True,
        "stats":      stats,
    })


def cmd_stats(args):
    api.setup()
    entry  = _ensure_session(args.workspace, args.user_id, False)
    result = api.get_stats(entry["user_id"])
    _print_json({
        "workspace":  entry["workspace"],
        "user_id":    entry["user_id"],
        "session_id": entry["session_id"],
        "turn":       entry["turn"],
        "stats":      result,
    })


def cmd_merge_db(args):
    _print_json(api.merge_db(target_db_path=args.target_db, source_db_path=args.source_db))


def cmd_rewrite_user_id(args):
    _print_json(api.rewrite_user_id(
        db_path     = args.db_path,
        new_user_id = args.new_user_id,
        old_user_id = args.old_user_id,
    ))


# ── 参数解析器 ────────────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        description="memory_skill_v3 · 会话 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
子命令速查：
  setup    检查 Redis / 嵌入服务 / SQLite 是否就绪
  ensure   初始化或恢复当前 workspace 的会话状态
  show     查看当前会话状态（不创建新会话）
  remember 检索与当前查询相关的历史记忆，返回 memory_text
  write    写入本轮摘要到热记忆，并递增 turn
  flush    归档热记忆到冷记忆（SQLite），清除 Redis 热记忆
  stats    查询当前用户冷记忆统计信息
  merge-db 将 source SQLite 中的记忆合并到 target SQLite
  rewrite-user-id 批量重写 SQLite 中的 user_id
""")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(p):
        p.add_argument("--workspace", required=True, help="项目工作目录路径")
        p.add_argument("--user-id", dest="user_id", help="用户唯一标识（默认 codex_<系统用户名>）")

    p = subparsers.add_parser("setup", help="检查依赖服务是否就绪")
    add_common(p); p.set_defaults(func=cmd_setup)

    p = subparsers.add_parser("ensure", help="初始化或恢复会话状态")
    add_common(p)
    p.add_argument("--reset", action="store_true", help="强制创建新会话")
    p.set_defaults(func=cmd_ensure)

    p = subparsers.add_parser("show", help="查看当前会话状态")
    add_common(p); p.set_defaults(func=cmd_show)

    p = subparsers.add_parser("remember", help="检索相关历史记忆")
    add_common(p)
    p.add_argument("--query", required=True, help="当前任务 / 问题文本")
    p.set_defaults(func=cmd_remember)

    p = subparsers.add_parser("write", help="写入本轮摘要到热记忆")
    add_common(p)
    p.add_argument("--question",      help="用户原始问题（直接传入）")
    p.add_argument("--question-file", dest="question_file", help="用户原始问题（从文件读取）")
    p.add_argument("--answer",        help="AI 回答（直接传入）")
    p.add_argument("--answer-file",   dest="answer_file",   help="AI 回答（从文件读取）")
    p.add_argument("--summary",       help="本轮摘要（直接传入）")
    p.add_argument("--summary-file",  dest="summary_file",  help="本轮摘要（从文件读取）")
    p.add_argument("--keywords-json", default="[]", dest="keywords_json",
                   help='关键词 JSON 数组或逗号分隔字符串')
    p.set_defaults(func=cmd_write)

    p = subparsers.add_parser("flush", help="归档热记忆到冷记忆并清除 Redis")
    add_common(p); p.set_defaults(func=cmd_flush)

    p = subparsers.add_parser("stats", help="查询用户冷记忆统计信息")
    add_common(p); p.set_defaults(func=cmd_stats)

    p = subparsers.add_parser("merge-db", help="将 source SQLite 中的记忆合并到 target SQLite")
    p.add_argument("--target-db", required=True, dest="target_db")
    p.add_argument("--source-db", required=True, dest="source_db")
    p.set_defaults(func=cmd_merge_db)

    p = subparsers.add_parser("rewrite-user-id", help="批量重写 SQLite 中的 user_id")
    p.add_argument("--db-path",     required=True, dest="db_path")
    p.add_argument("--new-user-id", required=True, dest="new_user_id")
    p.add_argument("--old-user-id", dest="old_user_id")
    p.set_defaults(func=cmd_rewrite_user_id)

    return parser


def main():
    parser = build_parser()
    args   = parser.parse_args()
    try:
        args.func(args)
    except SystemExit:
        raise
    except Exception as exc:
        _print_json({"ok": False, "error": str(exc)})
        _sys.stdout.flush()
        _sys.stderr.flush()
        _os._exit(1)

    _sys.stdout.flush()
    _sys.stderr.flush()

    # teardown 放守护线程：最多等 1 秒，之后无论是否结束都强制退出
    # 避免 redis-py socket.close() 在某些环境下阻塞主线程
    import threading
    def _teardown():
        try:
            api.teardown()
        except Exception:
            pass
    t = threading.Thread(target=_teardown, daemon=True)
    t.start()
    t.join(timeout=1)
    _os._exit(0)


if __name__ == "__main__":
    main()
