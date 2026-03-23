# Memory Skill 架构说明

## 目标

这套实现对齐 `othersys/skills/Claude.html` 的核心思路：
- Redis 存热记忆
- SQLite 存冷记忆
- 检索时热记忆全取、冷记忆双路召回
- 会话结束后再固化热记忆

## 模块分工

- [index.js](D:/mcsv3/othersys/skills/memory-skill/scripts/index.js)
  - 入口
  - 组装 runtime
  - 提供 CLI：`session-start / session-context / session-write / session-end / session-show / retrieve / prompt / write / persist`

- [core/retrieve.js](D:/mcsv3/othersys/skills/memory-skill/scripts/core/retrieve.js)
  - 读取 Redis 热记忆
  - 计算 query embedding
  - 优先执行 `sqlite-vec` 向量检索，失败时回退到 JS 余弦距离
  - 执行 FTS5 检索
  - 合并去重

- [core/inject.js](D:/mcsv3/othersys/skills/memory-skill/scripts/core/inject.js)
  - 生成带“本轮记忆 / 历史记忆”标识的 Prompt 片段
  - 用 token 预算裁剪

- [core/summarize.js](D:/mcsv3/othersys/skills/memory-skill/scripts/core/summarize.js)
  - 生成摘要和关键词
  - 做冲突判断
  - 合并相似记忆

- [core/write.js](D:/mcsv3/othersys/skills/memory-skill/scripts/core/write.js)
  - 为单轮问答生成记忆对象
  - 写入 Redis 热记忆

- [core/persist.js](D:/mcsv3/othersys/skills/memory-skill/scripts/core/persist.js)
  - 把 Session 热记忆固化到 SQLite 冷库

- [db/redis.js](D:/mcsv3/othersys/skills/memory-skill/scripts/db/redis.js)
  - Redis key 约定
  - 热记忆读写
  - Session 元数据和 turn 计数

- [utils/session_state.js](D:/mcsv3/othersys/skills/memory-skill/scripts/utils/session_state.js)
  - 管理当前激活会话
  - 让 skill 可以在“启用一次后”按固定 user/session 跑后续回合

- [db/sqlite.js](D:/mcsv3/othersys/skills/memory-skill/scripts/db/sqlite.js)
  - SQLite 建表
  - FTS5 触发器
  - 冷记忆 CRUD
  - `sqlite-vec` 扩展自动发现与加载
  - `memories_vec` 向量表同步
  - 向量相似度回退检索

- [utils/embedding.js](D:/mcsv3/othersys/skills/memory-skill/scripts/utils/embedding.js)
  - 支持 `sentence-transformers / openai / ollama / fallback`
  - 默认优先走本地 `sentence-transformers`

## 存储结构

Redis：
- `mem:hot:{user_id}:{session_id}:{turn}`
- `session:meta:{session_id}`
- `session:turns:{session_id}`

SQLite：
- `users`
- `sessions`
- `memories`
- `memories_fts`
- `memories_vec`（启用 `sqlite-vec` 时）

## 与方案的差异

这份实现保留了 `Claude.html` 的主体结构，但做了几处工程化修正：

- Redis 使用 `SCAN`，没有使用 `KEYS`
- FTS5 增加了 insert/update/delete 触发器，并对查询词做转义，避免路径和特殊字符触发 FTS 语法错误
- 默认优先使用 `sentence-transformers + sqlite-vec`，失败时回退到本地 JS 向量检索
- 没有把“直接 DELETE 旧记忆”做成唯一策略，而是保留“冲突则替换、相似则合并更新”的分支

## 适合的使用方式

- 本地助手
- 单用户 Agent
- 原型验证
- 小规模记忆实验

## 不适合的使用方式

- 大规模多租户平台
- 强合规场景
- 复杂审计和权限场景
