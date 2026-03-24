"""
memory_skill_v2 · 端到端测试
==============================
测试 AI 可调用接口：remember / memorize / flush。
使用真实的本地 embedding（sentence-transformers）。

不需要真实 AI，下载模型后不需要网络连接。

运行方式（在 memory_skill_v2 的上级目录执行）：
    python -m memory_skill_v2.test_skill
"""

import os
import sys
import tempfile

# 将 DB 重定向到临时文件，避免污染真实数据库
_tmp_fd, _tmp_db = tempfile.mkstemp(suffix=".db")
os.close(_tmp_fd)
os.environ["MEMORY_SQLITE_PATH"] = _tmp_db
os.environ["MEMORY_EMBED_DIM"]   = "384"

import memory_skill_v2 as skill


def sep(title=""):
    print("\n" + "-" * 60)
    if title:
        print(f"  {title}")
    print("-" * 60)


def test_setup():
    sep("TEST 1 · setup()")
    skill.setup()
    print("  PASS")


def test_remember_empty():
    sep("TEST 2 · remember() 在无记忆时返回空字符串")
    result = skill.remember(
        user_id    = "user_new",
        session_id = "session_new",
        turn       = 1,
        query_text = "第一次提问，什么记忆都没有",
    )
    assert result == "", f"Expected empty string, got: {repr(result)}"
    print("  PASS")


def test_memorize_and_hot_remember():
    sep("TEST 3 · memorize() 后 remember() 能命中热记忆")
    USER, SID = "user_a", "session_001"

    skill.memorize(
        user_id    = USER,
        session_id = SID,
        turn       = 1,
        summary    = "用户正在构建 AI 记忆系统，使用 Redis 和 SQLite",
        keywords   = ["Redis", "SQLite", "记忆系统", "AI"],
        raw_q      = "我想做一个记忆系统",
        raw_a      = "好的，推荐 Redis+SQLite 方案",
    )

    skill.memorize(
        user_id    = USER,
        session_id = SID,
        turn       = 2,
        summary    = "用户确认使用 Python，运行环境为 Windows",
        keywords   = ["Python", "Windows", "开发环境"],
        raw_q      = "我用 Python，Windows 系统",
        raw_a      = "没问题，pip install 即可",
    )

    context = skill.remember(
        user_id    = USER,
        session_id = SID,
        turn       = 3,
        query_text = "Redis 和 SQLite 怎么配合使用",
    )

    print("  Context returned:")
    print("  " + context.replace("\n", "\n  "))
    assert "第1轮" in context
    assert "第2轮" in context
    print("  PASS")


def test_flush_and_cold_remember():
    sep("TEST 4 · flush() 后在新 session 能命中冷记忆")
    USER, SID = "user_a", "session_001"

    stats = skill.flush(user_id=USER, session_id=SID)
    print(f"  Flush stats: {stats}")
    assert stats["inserted"] >= 2, f"Expected >= 2 inserts, got {stats}"

    context = skill.remember(
        user_id    = USER,
        session_id = "session_002",
        turn       = 1,
        query_text = "Redis SQLite 记忆系统搭配",
    )

    print("  Context in new session:")
    print("  " + context.replace("\n", "\n  "))
    assert "历史记忆" in context, "Expected cold memory block"
    print("  PASS")


def test_flush_merge():
    sep("TEST 5 · flush() 合并近似重复记忆")
    USER = "user_merge"

    skill.memorize(
        user_id=USER, session_id="s_a", turn=1,
        summary  = "用户偏好使用轻量本地部署方案，不想引入复杂依赖",
        keywords = ["轻量", "本地部署", "依赖"],
    )
    skill.flush(user_id=USER, session_id="s_a")

    skill.memorize(
        user_id=USER, session_id="s_b", turn=1,
        summary  = "用户仍然坚持轻量本地部署，明确排除云服务方案",
        keywords = ["轻量", "本地部署", "云服务"],
    )
    stats = skill.flush(user_id=USER, session_id="s_b")

    print(f"  Second flush stats: {stats}")
    assert stats["updated"] >= 1 or stats["inserted"] >= 1
    print("  PASS")


def test_get_stats():
    sep("TEST 6 · get_stats()")
    stats = skill.get_stats("user_a")
    print(f"  {stats}")
    assert stats["total_memories"] > 0
    assert stats["sessions"] > 0
    print("  PASS")


def test_empty_flush():
    sep("TEST 7 · 对不存在的 session 执行 flush() 返回全零")
    result = skill.flush("user_a", "session_nonexistent_xyz")
    assert result == {"inserted": 0, "updated": 0, "skipped": 0}
    print(f"  {result}")
    print("  PASS")


def run_all():
    tests = [
        test_setup,
        test_remember_empty,
        test_memorize_and_hot_remember,
        test_flush_and_cold_remember,
        test_flush_merge,
        test_get_stats,
        test_empty_flush,
    ]
    passed = 0
    failed = 0

    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"\n  FAIL: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    sep()
    print(f"  {passed} passed  /  {failed} failed")

    try:
        os.remove(_tmp_db)
    except Exception:
        pass

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    run_all()
