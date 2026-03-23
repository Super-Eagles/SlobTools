---
name: memory-skill
description: 用于构建或接入基于 Redis 热记忆 + SQLite 冷记忆的双层会话记忆能力，适合需要摘要、检索、Prompt 注入、会话固化的一体化本地方案。
---

# Memory Skill

## Overview

这个 skill 实现了一套贴近 `othersys/skills/Claude.html` 的轻量记忆方案：Redis 保存短期热记忆，SQLite 保存长期冷记忆，检索时走“热记忆全取 + 冷记忆向量/关键词双路召回”，会话结束后再把热记忆固化进冷库。

当前版本已经支持“会话模式”：
- 用户显式说“启用 `$memory-skill` 会话记忆”后，先执行一次 `session-start`
- 在该线程后续回合里，回答前优先执行 `session-context`
- 回答完成后执行 `session-write`
- 用户说“结束/关闭会话记忆”时执行 `session-end`

这意味着你不需要每一轮都手动指定 `userId/sessionId`，只需要在会话开始时启用一次。

适用场景：
- 需要给 Agent 或对话系统补“短期上下文 + 长期用户记忆”
- 希望本地优先、轻量部署，不引入重型向量数据库
- 需要把“摘要、写入、检索、注入、固化”做成一套可运行脚本

不适用场景：
- 多租户平台级记忆系统
- 需要严格审计、复杂权限、精细生命周期治理的生产平台

## Core Capabilities

### 0. 会话模式

这是推荐用法。高层命令都在 [index.js](D:/mcsv3/othersys/skills/memory-skill/scripts/index.js)：
- `session-start`
- `session-context`
- `session-write`
- `session-end`
- `session-show`

启用：

```bash
cd D:\mcsv3\othersys\skills\memory-skill\scripts
node index.js session-start --user u_demo --session s_demo --name demo --system "你是一个架构助手" --budget 500
```

取当前激活会话的记忆上下文：

```bash
node index.js session-context --question "帮我继续完善方案"
```

把本轮问答写回当前激活会话：

```bash
node index.js session-write --question "帮我继续完善方案" --answer "我已经把检索和固化链路补齐了"
```

结束并固化：

```bash
node index.js session-end
```

查看当前激活会话：

```bash
node index.js session-show
```

激活会话状态保存在 `scripts/data/active-session.json`，只用于本地会话驱动。

### 1. 写入热记忆

入口脚本是 [index.js](D:/mcsv3/othersys/skills/memory-skill/scripts/index.js) 的 `write` 命令，对单轮问答执行：
- 摘要生成
- 关键词提取
- 摘要向量化
- 写入 Redis `mem:hot:{user}:{session}:{turn}`

示例：

```bash
cd D:\mcsv3\othersys\skills\memory-skill\scripts
node index.js write --user u_demo --session s_demo --question "数据库用 redis+sqlite 吧" --answer "可以，这套组合轻量而且本地部署简单"
```

### 2. 检索相关记忆

[retrieve.js](D:/mcsv3/othersys/skills/memory-skill/scripts/core/retrieve.js) 会执行：
- 读取当前 Session 全部热记忆
- 对当前问题做 embedding
- 从 SQLite 做语义检索
- 用 FTS5 做关键词兜底
- 合并去重后输出 Top-K 冷记忆

示例：

```bash
node index.js retrieve --user u_demo --session s_demo --question "现在这套方案更适合本地部署吗"
```

### 3. 生成可注入 Prompt

[inject.js](D:/mcsv3/othersys/skills/memory-skill/scripts/core/inject.js) 把热记忆和冷记忆整理成明确标注的背景片段，避免模型把它们误当成本轮用户直接输入。

示例：

```bash
node index.js prompt --user u_demo --session s_demo --question "帮我继续完善方案" --system "你是一个架构助手" --budget 500
```

### 4. 固化 Session 记忆

[persist.js](D:/mcsv3/othersys/skills/memory-skill/scripts/core/persist.js) 会在 Session 结束时：
- 取出 Redis 热记忆
- 在 SQLite 中做相似记忆查找
- 判断是否冲突
- 执行插入、合并更新或替换
- 删除对应热记忆

示例：

```bash
node index.js persist --user u_demo --session s_demo
```

## Runtime Layout

实现代码位于 [scripts/](D:/mcsv3/othersys/skills/memory-skill/scripts)：
- [index.js](D:/mcsv3/othersys/skills/memory-skill/scripts/index.js)：统一入口，暴露 `retrieve / prompt / write / persist`
- [core/](D:/mcsv3/othersys/skills/memory-skill/scripts/core)：检索、注入、摘要、写入、固化逻辑
- [db/](D:/mcsv3/othersys/skills/memory-skill/scripts/db)：Redis / SQLite 访问层
- [utils/](D:/mcsv3/othersys/skills/memory-skill/scripts/utils)：配置、embedding、向量工具、token 预算

更详细的模块说明见 [architecture.md](D:/mcsv3/othersys/skills/memory-skill/references/architecture.md)。

## Environment

环境变量模板在 [scripts/.env.example](D:/mcsv3/othersys/skills/memory-skill/scripts/.env.example)。

关键项：
- `REDIS_URL`
- `SQLITE_PATH`
- `EMBED_PROVIDER`
- `SUMMARY_PROVIDER`
- `OPENAI_API_KEY`
- `MEMORY_TOP_K`
- `MEMORY_SIM_THRESHOLD`

默认行为：
- 没有配置 OpenAI 或 Ollama 时，会退回到本地 fallback 摘要/向量逻辑
- fallback 适合开发和演示，不适合高质量生产记忆

## Workflow

推荐工作流：

1. 启动 Redis，并准备 SQLite 路径。
2. 配置 embedding / summary provider。
3. 会话开始时调用 `session-start` 激活会话。
4. 每轮回答前调用 `session-context` 获取记忆上下文。
5. 回答完成后调用 `session-write` 写入热记忆。
6. 会话结束时调用 `session-end` 固化热记忆到冷库。

如果用户没有启用会话模式，再退回到底层命令：
- `retrieve`
- `prompt`
- `write`
- `persist`

## Notes

- 当前方案刻意保持轻量，向量检索默认走 SQLite 主表 + JS 余弦距离回退，不强依赖 `sqlite-vec` 扩展。
- Redis 扫描使用 `SCAN`，没有照抄 `Claude.html` 里的 `KEYS`，避免数据量起来后阻塞。
- SQLite FTS5 已做触发器同步，避免主表和全文索引不一致。
- 由于 skill 本身不是 Codex 底层消息钩子，所谓“自动记忆”是指：用户显式启用会话模式后，该线程内按约定自动走 `session-context -> 回答 -> session-write -> session-end` 这条流程。
