# ── 路径自配置（必须在所有本包导入之前）────────────────────────────────────
# 同时支持两种运行方式：
#   ① python -m memory_skill_v3.session_cli <cmd>   （模块方式，相对导入正常）
#   ② python /path/to/memory_skill_v3/session_cli.py <cmd>  （直接执行，自动修复路径）
import sys as _sys
import os as _os

try:
    from . import api  # 模块方式：相对导入
except ImportError:
    # 直接执行方式：把 memory_skill_v3 的上级目录加入 sys.path
    _pkg_parent = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    if _pkg_parent not in _sys.path:
        _sys.path.insert(0, _pkg_parent)
    from memory_skill_v3 import api  # type: ignore

# ── 正常导入 ──────────────────────────────────────────────────────────────────
import argparse
import getpass
import json
from datetime import datetime
from pathlib import Path


STATE_FILE = Path(__file__).with_name("active_sessions.json")


# ── 状态文件工具 ──────────────────────────────────────────────────────────────

def _normalize_workspace(workspace: str) -> str:
    return str(Path(workspace).resolve())


def _load_state():
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(data):
    STATE_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _default_user_id():
    return f"codex_{getpass.getuser()}"


def _new_session_id(workspace: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = Path(workspace).name or "workspace"
    safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name)
    return f"{safe_name}_{stamp}"


def _ensure_session(workspace: str, user_id: str | None = None, reset: bool = False):
    workspace = _normalize_workspace(workspace)
    state = _load_state()
    entry = state.get(workspace)

    if reset or entry is None:
        now = datetime.now().isoformat()
        entry = {
            "workspace": workspace,
            "user_id": user_id or _default_user_id(),
            "session_id": _new_session_id(workspace),
            "turn": 1,
            "created_at": now,
            "updated_at": now,
        }
        state[workspace] = entry
        _save_state(state)
        return entry

    if user_id and entry.get("user_id") != user_id:
        entry["user_id"] = user_id
        entry["updated_at"] = datetime.now().isoformat()
        state[workspace] = entry
        _save_state(state)

    return entry


def _update_entry(workspace: str, entry):
    workspace = _normalize_workspace(workspace)
    state = _load_state()
    entry["updated_at"] = datetime.now().isoformat()
    state[workspace] = entry
    _save_state(state)


def _remove_entry(workspace: str):
    workspace = _normalize_workspace(workspace)
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
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "gbk"):
        try:
            return target.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    return target.read_text(encoding="utf-8")


def _pick_text_arg(direct_value, file_value, field_name: str):
    if direct_value not in (None, ""):
        return direct_value
    if file_value not in (None, ""):
        return _read_text_file(file_value)
    raise SystemExit(f"{field_name} is required")


# ── 子命令处理函数 ────────────────────────────────────────────────────────────

def cmd_setup(args):
    """检查所有依赖服务是否就绪（Redis、嵌入模型/服务、SQLite）。"""
    try:
        api.setup()
        entry = _ensure_session(args.workspace, args.user_id, False)
        print(json.dumps({
            "ok": True,
            "workspace": entry["workspace"],
            "user_id": entry["user_id"],
            "session_id": entry["session_id"],
        }, ensure_ascii=False, indent=2))
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        raise SystemExit(1)


def cmd_ensure(args):
    entry = _ensure_session(args.workspace, args.user_id, args.reset)
    print(json.dumps(entry, ensure_ascii=False, indent=2))


def cmd_show(args):
    entry = _ensure_session(args.workspace, args.user_id, False)
    print(json.dumps(entry, ensure_ascii=False, indent=2))


def cmd_remember(args):
    api.setup()
    entry = _ensure_session(args.workspace, args.user_id, False)
    memory_text = api.remember(
        user_id=entry["user_id"],
        session_id=entry["session_id"],
        turn=int(entry["turn"]),
        query_text=args.query,
    )
    print(json.dumps({
        "workspace": entry["workspace"],
        "user_id": entry["user_id"],
        "session_id": entry["session_id"],
        "turn": entry["turn"],
        "memory_text": memory_text,
    }, ensure_ascii=False, indent=2))


def cmd_write(args):
    api.setup()
    entry = _ensure_session(args.workspace, args.user_id, False)
    question = _pick_text_arg(args.question, args.question_file, "question")
    answer   = _pick_text_arg(args.answer,   args.answer_file,   "answer")
    summary  = _pick_text_arg(args.summary,  args.summary_file,  "summary")
    keywords = _parse_keywords(args.keywords_json)
    mem_ids  = api.memorize(
        user_id    = entry["user_id"],
        session_id = entry["session_id"],
        turn       = int(entry["turn"]),
        summary    = summary,
        keywords   = keywords,
        raw_q      = question,
        raw_a      = answer,
    )
    entry["turn"] = int(entry["turn"]) + 1
    _update_entry(args.workspace, entry)
    print(json.dumps({
        "workspace": entry["workspace"],
        "user_id":   entry["user_id"],
        "session_id": entry["session_id"],
        "next_turn": entry["turn"],
        "mem_ids":   mem_ids,
    }, ensure_ascii=False, indent=2))


def cmd_flush(args):
    api.setup()
    entry = _ensure_session(args.workspace, args.user_id, False)
    stats = api.flush(
        user_id    = entry["user_id"],
        session_id = entry["session_id"],
    )
    _remove_entry(args.workspace)
    print(json.dumps({
        "workspace":  entry["workspace"],
        "user_id":    entry["user_id"],
        "session_id": entry["session_id"],
        "flushed":    True,
        "stats":      stats,
    }, ensure_ascii=False, indent=2))


def cmd_stats(args):
    """查询指定用户的冷记忆统计（总条数、历史会话数）。"""
    api.setup()
    entry  = _ensure_session(args.workspace, args.user_id, False)
    result = api.get_stats(entry["user_id"])
    print(json.dumps({
        "workspace":  entry["workspace"],
        "user_id":    entry["user_id"],
        "session_id": entry["session_id"],
        "turn":       entry["turn"],
        "stats":      result,
    }, ensure_ascii=False, indent=2))


def cmd_merge_db(args):
    result = api.merge_db(
        target_db_path=args.target_db,
        source_db_path=args.source_db,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


def cmd_rewrite_user_id(args):
    result = api.rewrite_user_id(
        db_path=args.db_path,
        new_user_id=args.new_user_id,
        old_user_id=args.old_user_id,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


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

示例（两种运行方式完全等价）：
  session_cli setup             --workspace .
  python session_cli.py setup   --workspace .
  python -m memory_skill_v3     setup   --workspace .
""")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(p):
        p.add_argument("--workspace", required=True,
                       help="项目工作目录路径（同一项目保持不变）")
        p.add_argument("--user-id", dest="user_id",
                       help="用户唯一标识（默认 codex_<系统用户名>）")

    # setup
    p_setup = subparsers.add_parser("setup", help="检查依赖服务是否就绪")
    add_common(p_setup)
    p_setup.set_defaults(func=cmd_setup)

    # ensure
    p_ensure = subparsers.add_parser("ensure", help="初始化或恢复会话状态")
    add_common(p_ensure)
    p_ensure.add_argument("--reset", action="store_true",
                          help="强制创建新会话（清除旧 session_id）")
    p_ensure.set_defaults(func=cmd_ensure)

    # show
    p_show = subparsers.add_parser("show", help="查看当前会话状态")
    add_common(p_show)
    p_show.set_defaults(func=cmd_show)

    # remember
    p_remember = subparsers.add_parser("remember", help="检索相关历史记忆")
    add_common(p_remember)
    p_remember.add_argument("--query", required=True,
                            help="当前任务 / 问题文本，用于语义检索")
    p_remember.set_defaults(func=cmd_remember)

    # write
    p_write = subparsers.add_parser("write", help="写入本轮摘要到热记忆")
    add_common(p_write)
    p_write.add_argument("--question",      help="用户原始问题（直接传入）")
    p_write.add_argument("--question-file", help="用户原始问题（从文件读取）")
    p_write.add_argument("--answer",        help="AI 回答（直接传入）")
    p_write.add_argument("--answer-file",   help="AI 回答（从文件读取）")
    p_write.add_argument("--summary",       help="本轮摘要（直接传入）")
    p_write.add_argument("--summary-file",  help="本轮摘要（从文件读取）")
    p_write.add_argument("--keywords-json", default="[]",
                         help='关键词 JSON 数组，如 \'["Redis","缓存"]\' 或逗号分隔字符串')
    p_write.set_defaults(func=cmd_write)

    # flush
    p_flush = subparsers.add_parser("flush", help="归档热记忆到冷记忆并清除 Redis")
    add_common(p_flush)
    p_flush.set_defaults(func=cmd_flush)

    # stats
    p_stats = subparsers.add_parser("stats", help="查询用户冷记忆统计信息")
    add_common(p_stats)
    p_stats.set_defaults(func=cmd_stats)

    # merge-db
    p_merge_db = subparsers.add_parser("merge-db", help="将 source SQLite 中的记忆合并到 target SQLite")
    p_merge_db.add_argument("--target-db", required=True, help="目标数据库路径，例如 memory.db")
    p_merge_db.add_argument("--source-db", required=True, help="来源数据库路径，例如 memory1.db")
    p_merge_db.set_defaults(func=cmd_merge_db)

    # rewrite-user-id
    p_rewrite_uid = subparsers.add_parser("rewrite-user-id", help="批量重写 SQLite 中的 user_id")
    p_rewrite_uid.add_argument("--db-path", required=True, help="数据库路径，例如 memory.db")
    p_rewrite_uid.add_argument("--new-user-id", required=True, help="新的 user_id")
    p_rewrite_uid.add_argument("--old-user-id", help="仅替换指定旧 user_id；不传则替换库内全部 user_id")
    p_rewrite_uid.set_defaults(func=cmd_rewrite_user_id)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
