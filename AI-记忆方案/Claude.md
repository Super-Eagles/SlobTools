以下是我认为可上线的最优方案：

---

## 核心原则

> 记忆系统的本质是 **"存什么、怎么找"**，而不只是"往哪里存"。
> 最大的坑是：存了很多，但检索时找不到对的。---

## 数据结构设计

**每条记忆存什么：**

```json
{
  "id": "uuid",
  "user_id": "u_123",
  "session_id": "s_456",
  "turn": 3,
  "summary": "用户正在构建 AI 记忆 skill，偏好轻量本地方案，技术栈倾向 Node.js",
  "keywords": ["AI记忆", "Redis", "SQLite", "轻量部署"],
  "embedding": [0.12, 0.87, ...],
  "raw_q": "数据库用redis+sqlite吧",
  "raw_a": "好，Redis + SQLite 组合非常轻量...",
  "created_at": "2026-03-23T10:00:00Z"
}
```

**关键点：摘要由 AI 自己生成**（每轮对话后追加一个小 prompt），不是原始对话文本，这样检索精度高很多。

---

## 存储层设计

| 层 | 技术 | 存什么 | 检索方式 | 生命周期 |
|---|---|---|---|---|
| 热记忆 | Redis | 本轮所有对话摘要 | 按 session_id 全取 | TTL 24h，session 结束主动固化 |
| 冷记忆 | SQLite + sqlite-vec | 全部历史摘要 + 向量 | 向量相似度 Top-5 | 永久 |
| 兜底 | SQLite FTS5 | 同上 | 关键词全文检索 | 永久 |

> 检索策略：**向量精排 + FTS 兜底**，两者结果合并去重后取 Top-5 注入 prompt。

---

## Prompt 注入格式

```
你拥有以下长期记忆，请在回答时参考：

[记忆 1 - 2026-03-20] 用户正在构建 AI 记忆 skill，偏好轻量本地方案
[记忆 2 - 2026-03-21] 用户技术栈为 Node.js，熟悉 Redis 和 SQLite
[本轮记忆] 用户本轮讨论了 Redis+SQLite 方案，确认使用 FTS5 先跑通流程

用户问题：xxx
```

**注入量控制：历史记忆最多 5 条，本轮记忆全量**，避免 context 溢出。

---

## 记忆更新机制（关键，常被忽略）

不是只追加，而是**三种操作**：

```
每轮写入前，AI 判断：

新信息  → INSERT 新记忆
更新信息 → UPDATE 旧记忆（如用户改变了偏好）
矛盾信息 → DELETE 旧记忆 + INSERT 新记忆
```

这样避免 "用户说了三个月前喜欢 A，两个月前改成 B，AI 还记得 A" 的问题。

---

## 文件结构

```
memory-skill/
├── SKILL.md
├── index.js          # 入口，串联所有模块
├── retrieve.js       # 检索：Redis全取 + SQLite向量/FTS
├── inject.js         # 拼装记忆注入 prompt
├── summarize.js      # 调 AI 生成摘要+关键词+向量
├── write.js          # 写入 Redis 热记忆
├── persist.js        # 固化：Redis → SQLite
└── db.js             # SQLite 建表 + sqlite-vec 初始化
```

---

## 依赖清单（极简）

```
ioredis          # Redis 客户端
better-sqlite3   # SQLite
sqlite-vec       # 向量检索扩展
```

Embedding 服务：优先 `text-embedding-3-small`（OpenAI），本地可用 `nomic-embed-text`（Ollama）。

---

**这个方案可以直接上线的原因：**
- 无额外服务依赖，本地一机搞定
- 向量 + FTS 双保险，检索覆盖率高
- 记忆有更新/删除机制，不会越存越乱
- 注入量有控制，不会撑爆 context

要开始写实现吗？