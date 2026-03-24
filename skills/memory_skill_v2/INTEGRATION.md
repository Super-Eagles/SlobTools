# memory_skill_v2 接入指南

为任意 AI Agent 添加跨会话长期记忆能力。支持 OpenAI、Anthropic、Google、本地模型等所有框架。

---

## 目录

1. [原理](#原理)
2. [环境要求](#环境要求)
3. [安装](#安装)
4. [初始化](#初始化)
5. [API 参考](#api-参考)
6. [接入模式](#接入模式)
   - [最小接入](#最小接入)
   - [推荐接入（带自动摘要）](#推荐接入带自动摘要)
   - [OpenAI 完整示例](#openai-完整示例)
   - [Anthropic 完整示例](#anthropic-完整示例)
7. [摘要生成策略](#摘要生成策略)
8. [配置项](#配置项)
9. [常见问题](#常见问题)

---

## 原理

```
每轮对话开始            每轮对话结束
       ↓                      ↓
  remember()             memorize()
  向量检索历史记忆         写入本轮摘要
  注入 system prompt      存入 Redis（热）

                    会话结束
                         ↓
                      flush()
                    Redis → SQLite（冷）
                    自动去重合并
```

**热存储（Redis）**：当前会话的记忆，按 TTL 自动过期，检索速度极快。

**冷存储（SQLite + sqlite-vec）**：持久化的跨会话记忆，通过向量相似度 + 全文检索双路召回。

---

## 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | ≥ 3.10 | |
| Redis | ≥ 6.0 | 热存储，必须在线 |
| sqlite-vec | ≥ 0.1.6 | 向量检索扩展，pip 安装 |
| sentence-transformers | ≥ 3.0 | embedding 模型，首次运行下载 ~470 MB |

**启动 Redis：**

```bash
# macOS
brew install redis && brew services start redis

# Linux
sudo apt install redis-server && sudo systemctl start redis

# Windows
# 安装 Memurai：https://www.memurai.com/
```

---

## 安装

将 `memory_skill_v2/` 目录放到你的项目中，然后安装依赖：

```bash
pip install -r memory_skill_v2/requirements.txt
```

目录结构不影响导入，只需确保 `memory_skill_v2/` 在 Python 路径内：

```
your_project/
├── memory_skill_v2/   ← 放在这里
│   ├── SKILL.md
│   ├── api.py
│   ├── core/
│   ├── db/
│   └── utils/
└── your_bot.py
```

---

## 初始化

程序启动时调用一次，检查所有依赖是否就绪：

```python
import memory_skill_v2 as mem

mem.setup()
# [memory-skill] SQLite ready · sqlite-vec 0.1.6
# [memory-skill] Redis ready.
# [memory-skill] Embedding model ready.
# [memory-skill] Setup complete.
```

---

## API 参考

### `remember(user_id, session_id, turn, query_text) → str`

检索与当前问题相关的历史记忆，返回格式化文本块。

```python
context = mem.remember(
    user_id    = "user_001",       # 用户唯一标识，记忆按用户隔离
    session_id = "session_abc",    # 当前会话 ID
    turn       = 3,                # 当前轮次（整数，从 1 开始）
    query_text = "用户这轮的问题",  # 用于向量检索，越贴近用户原话越好
)
# 返回字符串，无相关记忆时返回空字符串 ""
```

返回示例：
```
你拥有以下记忆。请在回答时自然地结合这些背景，不要直接说根据我的记忆：

【历史记忆】
  [2026-03-20] 用户正在构建 Python 聊天机器人，偏好轻量方案
  [2026-03-22] 用户已确定使用 Redis + SQLite 做记忆存储

【本轮对话】
  [第1轮] 用户询问了 LangChain 和 LlamaIndex 的区别
  [第2轮] 用户决定使用 LlamaIndex，关注 RAG 流程

---
```

### `memorize(user_id, session_id, turn, summary, keywords, raw_q, raw_a) → str`

将本轮对话写入 Redis 热存储，返回记忆 ID。

```python
mem_id = mem.memorize(
    user_id    = "user_001",
    session_id = "session_abc",
    turn       = 3,
    summary    = "用户询问了 Python 异步编程最佳实践",  # 一句话摘要，越准确召回越好
    keywords   = ["Python", "异步", "async", "最佳实践"],  # 3-6 个关键词
    raw_q      = "用户原始问题",   # 可选，存档用
    raw_a      = "AI 原始回答",    # 可选，存档用
)
```

> **注意**：相同 `(user_id, session_id, turn)` 重复写入会覆盖之前的记录。

### `flush(user_id, session_id) → dict`

将热记忆持久化到 SQLite，自动去重合并。会话结束时必须调用。

```python
stats = mem.flush("user_001", "session_abc")
# → {"inserted": 3, "updated": 1, "skipped": 0}
```

| 字段 | 含义 |
|------|------|
| `inserted` | 新增的记忆条数 |
| `updated` | 与已有记忆合并（更新）的条数 |
| `skipped` | 跳过的条数（无 embedding 数据） |

### `get_stats(user_id) → dict`

查询用户的记忆统计。

```python
mem.get_stats("user_001")
# → {"total_memories": 42, "sessions": 7}
```

---

## 接入模式

### 最小接入

最简单的接入方式，适合快速验证：

```python
import memory_skill_v2 as mem

mem.setup()

def chat(user_id: str, session_id: str, turn: int, user_message: str, llm_func) -> str:
    # 1. 取出记忆，拼入 system prompt
    context = mem.remember(user_id, session_id, turn, user_message)
    system  = (context + "\n\n" if context else "") + "你是一个有帮助的助手。"

    # 2. 调用任意 LLM（你自己的封装）
    answer = llm_func(system=system, user=user_message)

    # 3. 手动写入摘要（简单版：直接截断用户问题作摘要）
    mem.memorize(
        user_id    = user_id,
        session_id = session_id,
        turn       = turn,
        summary    = user_message[:100],  # 简单截断，效果一般
        keywords   = [],
    )
    return answer
```

---

### 推荐接入（带自动摘要）

让模型自动生成高质量摘要，召回效果显著更好：

```python
import json
import memory_skill_v2 as mem

mem.setup()

SUMMARY_SYSTEM = """你的任务是为一段对话生成记忆摘要。
只返回 JSON，不要有任何其他内容，格式：
{"summary": "一句话描述本轮对话的核心信息", "keywords": ["关键词1", "关键词2", "关键词3"]}
要求：
- summary 控制在 50 字以内，突出用户的意图、偏好、决策
- keywords 3-6 个，中英文均可
- 不要输出 JSON 以外的任何文字"""


def build_memory_meta(q: str, a: str, llm_func) -> dict:
    """调用轻量模型生成摘要，失败时降级为截断。"""
    try:
        raw = llm_func(
            system = SUMMARY_SYSTEM,
            user   = f"Q: {q}\nA: {a}",
        )
        return json.loads(raw)
    except Exception:
        return {"summary": q[:80], "keywords": []}


def chat(user_id: str, session_id: str, turn: int, user_message: str,
         main_llm, summary_llm=None) -> str:
    summary_llm = summary_llm or main_llm

    # 1. 检索记忆
    context = mem.remember(user_id, session_id, turn, user_message)
    system  = (context + "\n\n" if context else "") + "你是一个专业助手。"

    # 2. 主模型回答
    answer = main_llm(system=system, user=user_message)

    # 3. 生成摘要（用轻量模型节省成本）
    meta = build_memory_meta(user_message, answer, summary_llm)

    # 4. 写入记忆
    mem.memorize(
        user_id    = user_id,
        session_id = session_id,
        turn       = turn,
        summary    = meta["summary"],
        keywords   = meta["keywords"],
        raw_q      = user_message,
        raw_a      = answer,
    )
    return answer
```

---

### OpenAI 完整示例

```python
import json
from openai import OpenAI
import memory_skill_v2 as mem

mem.setup()
client = OpenAI()  # 默认读取 OPENAI_API_KEY 环境变量

SUMMARY_SYSTEM = """只返回 JSON，格式：
{"summary": "本轮对话核心信息（50字内）", "keywords": ["词1","词2","词3"]}"""


def chat(user_id: str, session_id: str, turn: int, user_message: str) -> str:
    # 1. 检索记忆
    context = mem.remember(user_id, session_id, turn, user_message)
    messages = []
    if context:
        messages.append({"role": "system", "content": context})
    messages.append({"role": "user", "content": user_message})

    # 2. 主模型回答
    resp   = client.chat.completions.create(model="gpt-4o", messages=messages)
    answer = resp.choices[0].message.content

    # 3. 生成摘要
    meta_resp = client.chat.completions.create(
        model    = "gpt-4o-mini",  # 用小模型降低成本
        messages = [
            {"role": "system", "content": SUMMARY_SYSTEM},
            {"role": "user",   "content": f"Q: {user_message}\nA: {answer}"},
        ],
    )
    try:
        meta = json.loads(meta_resp.choices[0].message.content)
    except Exception:
        meta = {"summary": user_message[:80], "keywords": []}

    # 4. 写入记忆
    mem.memorize(user_id, session_id, turn,
        summary  = meta["summary"],
        keywords = meta["keywords"],
        raw_q    = user_message,
        raw_a    = answer,
    )
    return answer


# 使用
mem.setup()
uid, sid = "user_001", "session_20260324"

print(chat(uid, sid, 1, "我想用 Python 构建一个 AI 记忆系统"))
print(chat(uid, sid, 2, "有没有轻量一点的方案？"))  # 会召回第 1 轮记忆
print(chat(uid, sid, 3, "Redis 需要持久化配置吗？"))

mem.flush(uid, sid)  # 会话结束，持久化
```

---

### Anthropic 完整示例

```python
import json
import anthropic
import memory_skill_v2 as mem

client = anthropic.Anthropic()  # 默认读取 ANTHROPIC_API_KEY 环境变量

SUMMARY_SYSTEM = """只返回 JSON，格式：
{"summary": "本轮对话核心信息（50字内）", "keywords": ["词1","词2","词3"]}"""


def chat(user_id: str, session_id: str, turn: int, user_message: str) -> str:
    # 1. 检索记忆
    context = mem.remember(user_id, session_id, turn, user_message)
    system  = (context + "\n\n" if context else "") + "你是一个专业助手。"

    # 2. 主模型回答
    resp   = client.messages.create(
        model    = "claude-sonnet-4-6",
        max_tokens = 1024,
        system   = system,
        messages = [{"role": "user", "content": user_message}],
    )
    answer = resp.content[0].text

    # 3. 生成摘要（用 Haiku 节省成本）
    meta_resp = client.messages.create(
        model    = "claude-haiku-4-5-20251001",
        max_tokens = 150,
        system   = SUMMARY_SYSTEM,
        messages = [{"role": "user", "content": f"Q: {user_message}\nA: {answer}"}],
    )
    try:
        meta = json.loads(meta_resp.content[0].text)
    except Exception:
        meta = {"summary": user_message[:80], "keywords": []}

    # 4. 写入记忆
    mem.memorize(user_id, session_id, turn,
        summary  = meta["summary"],
        keywords = meta["keywords"],
        raw_q    = user_message,
        raw_a    = answer,
    )
    return answer


# 使用
mem.setup()
uid, sid = "user_001", "session_20260324"

print(chat(uid, sid, 1, "我想用 Python 构建一个 AI 记忆系统"))
print(chat(uid, sid, 2, "有没有轻量一点的方案？"))
print(chat(uid, sid, 3, "Redis 需要持久化配置吗？"))

mem.flush(uid, sid)
```

---

## 摘要生成策略

`summary` 的质量直接决定记忆的召回效果，以下是三种常见策略：

| 策略 | 适用场景 | 效果 |
|------|----------|------|
| **截断用户输入** | 原型阶段，快速验证 | 一般 |
| **调用轻量模型生成** | 生产环境推荐 | 好 |
| **在主模型 response 中一并生成** | 减少 API 调用次数 | 好，但耦合主回答 |

**在主模型中一并生成摘要（节省一次 API 调用）：**

```python
system = context + """

你是一个专业助手。回答完用户问题后，在最后另起一行输出：
<memory>{"summary":"...","keywords":[...]}</memory>
这部分不会展示给用户。"""

# 解析回答和记忆块
import re
raw    = resp.content[0].text
match  = re.search(r"<memory>(.*?)</memory>", raw, re.DOTALL)
answer = raw[:match.start()].strip() if match else raw
meta   = json.loads(match.group(1)) if match else {"summary": answer[:80], "keywords": []}
```

---

## 配置项

所有配置通过环境变量覆盖，无需修改代码：

```bash
export MEMORY_REDIS_URL="redis://localhost:6379"   # Redis 地址
export MEMORY_SQLITE_PATH="./memory.db"            # 数据库路径（相对于 skill 目录）
export MEMORY_EMBED_MODEL="paraphrase-multilingual-MiniLM-L12-v2"  # embedding 模型
export MEMORY_EMBED_DIM="384"         # 向量维度，须与模型一致
export MEMORY_TOP_K="5"               # 每次最多召回的冷记忆条数
export MEMORY_SIM_THRESHOLD="0.75"    # 向量检索相似度下限（调高=更精确，调低=更多召回）
export MEMORY_MERGE_THRESHOLD="0.88"  # 去重合并阈值（调高=保留更多细节）
export MEMORY_SESSION_TTL="86400"     # Redis 热记忆过期时间（秒）
```

---

## 常见问题

**Q：flush() 之前程序崩溃，记忆会丢失吗？**

热记忆在 Redis 中有 TTL（默认 24 小时），TTL 内重启不丢失。可在程序入口注册 `atexit` 钩子保险：

```python
import atexit
atexit.register(lambda: mem.flush(user_id, session_id))
```

**Q：多用户并发安全吗？**

同一进程内多线程安全（SQLite 写入有锁保护）。跨进程并发写入同一数据库需改用 WAL 模式：

```python
conn = mem.db.sqlite_db.get_conn()
conn.execute("PRAGMA journal_mode=WAL")
```

**Q：如何清空某用户的所有记忆？**

```python
conn = mem.db.sqlite_db.get_conn()
conn.execute("DELETE FROM memories WHERE user_id = ?", ("user_001",))
conn.commit()
```

**Q：更换 embedding 模型怎么办？**

更换模型后旧向量与新向量不兼容，需重建数据库：删除 `memory.db`，下次启动自动重建（历史记忆丢失）。建议生产环境确定模型后不再更换。

**Q：想用远程 Redis（如 Redis Cloud）？**

```bash
export MEMORY_REDIS_URL="redis://:password@your-host:6379"
# 或 TLS：
export MEMORY_REDIS_URL="rediss://:password@your-host:6380"
```
