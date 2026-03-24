---
name: memory
description: >
  为 AI Agent 提供跨会话长期记忆能力。每当对话涉及"记住用户偏好/历史"、
  "上次说过…"、"记得我之前提到…"、需要个性化回复、或任何需要在多轮/多次
  对话间保持上下文的场景，都应使用此 skill。
  包含四个操作：remember（检索注入）、memorize（写入）、flush（持久化）、
  get_stats（统计）。只要对话需要记忆能力，务必调用此 skill，不要依赖上下文窗口。
compatibility: "需要 Redis 在线；SQLite 自动初始化；首次运行会下载 embedding 模型 (~470 MB)"
---

# Memory Skill

为 AI Agent 提供热记忆（Redis，当前会话）+ 冷记忆（SQLite + 向量检索，跨会话持久化）的双层存储，并支持自动去重合并。

## 快速上手

```python
import memory_skill_v2 as skill
```

**首次使用前必须调用一次：**
```python
skill.setup()   # 检查 Redis、SQLite、embedding 模型
```

---

## 四个核心函数

### 1. `remember()` — 每轮对话**开始前**调用

检索与当前问题相关的历史记忆，返回格式化文本块，直接拼入 system prompt。

```python
context = skill.remember(
    user_id    = "user_001",      # 用户唯一标识
    session_id = "session_abc",   # 当前会话 ID
    turn       = 3,               # 当前是第几轮
    query_text = "用户这轮的问题", # 用于向量检索相关历史
)
# context 是字符串，空字符串表示无相关记忆
# 将 context 拼入 system_prompt：
system_prompt = context + "\n\n你是一个助手..."
```

### 2. `memorize()` — 每轮对话**结束后**调用

将本轮对话的摘要写入 Redis 热存储。`summary` 和 `keywords` 推荐让模型自动生成。

```python
skill.memorize(
    user_id    = "user_001",
    session_id = "session_abc",
    turn       = 3,
    summary    = "用户询问了 Python 异步编程最佳实践",  # 一句话摘要
    keywords   = ["Python", "异步", "async"],           # 3-6 个关键词
    raw_q      = "原始用户问题（可选）",
    raw_a      = "原始 AI 回答（可选）",
)
```

### 3. `flush()` — 会话**结束时**调用

将 Redis 热记忆持久化到 SQLite，自动去重/合并相似记忆。

```python
stats = skill.flush("user_001", "session_abc")
# → {"inserted": 3, "updated": 1, "skipped": 0}
```

### 4. `get_stats()` — 按需查询

```python
skill.get_stats("user_001")
# → {"total_memories": 42, "sessions": 7}
```

---

## 标准接入模式

每轮对话的调用顺序固定为：

```
用户发消息
    → remember()        # 取出相关记忆
    → 拼入 system prompt
    → 调用 LLM 生成回答
    → memorize()        # 存入本轮摘要
    → 返回回答给用户

会话结束
    → flush()           # 热记忆 → 冷记忆
```

### 完整示例

```python
import memory_skill_v2 as skill
import anthropic

skill.setup()
client = anthropic.Anthropic()

def chat(user_id: str, session_id: str, turn: int, user_message: str) -> str:
    # 1. 检索记忆，注入 prompt
    memory_context = skill.remember(user_id, session_id, turn, user_message)
    system = (memory_context + "\n\n" if memory_context else "") + "你是一个专业助手。"

    # 2. 调用模型
    resp = client.messages.create(
        model      = "claude-sonnet-4-6",
        max_tokens = 1024,
        system     = system,
        messages   = [{"role": "user", "content": user_message}],
    )
    answer = resp.content[0].text

    # 3. 生成摘要和关键词（用低成本模型即可）
    meta = client.messages.create(
        model      = "claude-haiku-4-5-20251001",
        max_tokens = 150,
        system     = '只返回 JSON，格式：{"summary":"...","keywords":["..."]}',
        messages   = [{"role": "user", "content": f"Q: {user_message}\nA: {answer}"}],
    )
    import json
    m = json.loads(meta.content[0].text)

    # 4. 写入记忆
    skill.memorize(user_id, session_id, turn,
        summary  = m["summary"],
        keywords = m["keywords"],
        raw_q    = user_message,
        raw_a    = answer,
    )
    return answer
```

---

## 关键参数说明

| 参数 | 说明 |
|------|------|
| `user_id` | 用户唯一标识，记忆按用户隔离 |
| `session_id` | 会话 ID，热记忆按会话隔离，flush 时以此为单位持久化 |
| `turn` | 当前轮次（整数，从 1 开始），用于热记忆排序 |
| `summary` | 本轮核心信息的一句话描述，是检索的主要依据，写得越准确召回越好 |
| `keywords` | 3-6 个关键词，辅助全文检索，中英文均可 |

## 可调阈值（环境变量）

| 变量 | 默认 | 说明 |
|------|------|------|
| `MEMORY_SIM_THRESHOLD` | 0.75 | 冷记忆向量检索相似度下限，调高则更精确，调低则召回更多 |
| `MEMORY_MERGE_THRESHOLD` | 0.88 | 去重合并阈值，调高则更少合并，保留更多细节 |
| `MEMORY_TOP_K` | 5 | 每次最多召回的冷记忆条数 |
| `MEMORY_SESSION_TTL` | 86400 | Redis 热记忆过期时间（秒），默认 24 小时 |

---

## 注意事项

- `remember()` 返回空字符串时表示暂无相关记忆，直接忽略即可，不要拼入 prompt
- `flush()` 之前热记忆仅存在于 Redis，TTL 到期会丢失；重要会话结束后务必 flush
- 相同 `(user_id, session_id, turn)` 的 `memorize()` 会覆盖之前的写入（Redis setex 行为）
- 首次 `setup()` 会下载 ~470 MB 的 embedding 模型，之后缓存到本地无需重复下载
