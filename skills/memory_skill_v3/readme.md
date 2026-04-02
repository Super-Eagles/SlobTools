# memory_skill_v3

一个给对话系统增加长短期记忆的 Python 包。

它的核心目标很简单：
- 当前会话中的关键信息先写入 Redis 热记忆
- 会话结束后再刷入 SQLite 冷记忆
- 下次对话开始时，优先把相关历史记忆检索出来，作为回答背景

这个 README 是给人看的项目说明，不是给 AI 的系统提示词。

## 1. 项目概览

`memory_skill_v3` 主要解决 3 件事：

1. 记住当前会话刚刚发生过什么
2. 记住跨会话仍然有价值的稳定信息
3. 在后续对话中把相关记忆自然注入到 prompt

当前实现分成两层存储：
- 热记忆：Redis，保存当前 session 的临时记忆，带 TTL
- 冷记忆：SQLite + sqlite-vec，保存长期记忆，支持向量检索和 FTS 补充检索

标准流程是：

```text
remember -> 回答 -> write/memorize -> flush
```

其中：
- `remember` 负责取回相关背景
- `write` / `memorize` 负责把本轮摘要写入热记忆
- `flush` 负责把热记忆落到长期库

## 2. 目录结构

```text
memory_skill_v3/
├── MEMORY_AGENT_SYSTEM_PROMPT.md   # 给 AI 用的直接执行协议
├── session_cli.py                  # 主要 CLI 入口
├── api.py                          # 底层 API
├── chat_wrapper.py                 # 会话封装器
├── embed_server.py                 # 向量嵌入服务
├── maintenance.py                  # 数据库维护能力
├── config.py                       # 配置
├── qry.py                          # 调试查看 Redis / SQLite
├── core/                           # 检索、写入、持久化、注入逻辑
├── db/                             # Redis / SQLite 访问层
└── utils/                          # embedding / vector 工具
```

## 3. 依赖与运行环境

### 必需组件

- Python 3.11+ 推荐
- Redis 或 Memurai
- SQLite

### Python 依赖

仓库里的 `requirements.txt` 只列了核心包：

```bash
pip install -r requirements.txt
```

如果你要使用远程 embedding 服务，额外安装：

```bash
pip install requests fastapi uvicorn pydantic
```

如果你要本地加载嵌入模型，还需要：

```bash
pip install torch
```

说明：
- `sentence-transformers` 会依赖 PyTorch，但在某些环境下最好显式安装
- 首次加载 `paraphrase-multilingual-MiniLM-L12-v2` 会下载模型，体积大约 470 MB

## 4. 环境变量

这一节是给你配置环境用的，不是给 AI 提示词用的。

### 推荐配置

Windows：

```cmd
setx PATH "%PATH%;C:\memory_skill_v3"
setx MEMORY_SKILL_DIR "C:\memory_skill_v3"
setx MEMORY_SQLITE_PATH "C:\memory_skill_v3\memory.db"
setx MEMORY_REDIS_URL "redis://localhost:6379"
setx MEMORY_EMBED_SERVICE_URL "http://127.0.0.1:7731"
```

说明：
- 把 `C:\memory_skill_v3` 加进 `PATH` 后，可以在任意目录直接执行 `session_cli`
- `MEMORY_SKILL_DIR` 主要方便你在别处引用本项目路径
- `MEMORY_SQLITE_PATH` 建议写绝对路径，避免数据库落到意料之外的位置
- 当前代码默认会优先按远程 embedding 服务模式运行，所以推荐把服务启动起来

### 如果你不想启用 embedding 服务

当前终端临时清空：

```cmd
set MEMORY_EMBED_SERVICE_URL=
```

然后再运行命令。

注意：
- 这是当前终端生效
- 如果你已经用 `setx` 写入了永久环境变量，开新终端后仍会恢复

### 常用配置项

| 环境变量 | 默认值 | 作用 |
| --- | --- | --- |
| `MEMORY_REDIS_URL` | `redis://localhost:6379` | Redis 地址 |
| `MEMORY_SQLITE_PATH` | `./memory.db` | SQLite 文件路径 |
| `MEMORY_EMBED_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | embedding 模型 |
| `MEMORY_EMBED_DIM` | `384` | 向量维度 |
| `MEMORY_EMBED_SERVICE_URL` | `http://127.0.0.1:7731` | embedding 服务地址 |
| `MEMORY_TOP_K` | `5` | 冷记忆召回条数 |
| `MEMORY_SIM_THRESHOLD` | `0.75` | 检索相似度阈值 |
| `MEMORY_MERGE_THRESHOLD` | `0.88` | flush 时合并阈值 |
| `MEMORY_SESSION_TTL` | `86400` | 热记忆 TTL |
| `MEMORY_TOKEN_BUDGET` | `1200` | 注入 prompt 的记忆预算 |

## 5. 快速开始

### 5.1 启动 Redis

Windows（Memurai）：

```cmd
net start memurai
```

Linux：

```bash
redis-server --daemonize yes
```

### 5.2 启动 embedding 服务

推荐单独开一个终端：

```cmd
cd /d C:\memory_skill_v3
python embed_server.py
```

### 5.3 做一次健康检查

这是给开发者用的，不是给 AI 每轮都执行的。

```cmd
cd /d C:\memory_skill_v3
python session_cli.py setup --workspace .
```

如果返回里有 `"ok": true`，说明 Redis、SQLite、embedding 服务都能连通。

## 6. CLI 用法

主入口：

```cmd
session_cli <command> [options]
```

也支持模块方式：

```cmd
python -m memory_skill_v3 <command> [options]
```

### 6.1 初始化会话

```cmd
session_cli ensure --workspace C:\your_project
```

作用：
- 给当前 `workspace` 建立一个活动会话
- 自动生成 `user_id`
- 自动生成 `session_id`
- 初始化 `turn = 1`

如果同一个 `workspace` 已经有活动会话，再次调用会复用它。

### 6.2 检索记忆

```cmd
session_cli remember --workspace C:\your_project --query "用户当前输入"
```

返回 JSON 里最重要的字段是：
- `memory_text`
- `turn`

其中 `memory_text` 可以直接拼进你的 system prompt。

### 6.3 写入本轮摘要

```cmd
session_cli write --workspace C:\your_project ^
  --question "用户问了什么" ^
  --answer "AI 回答了什么" ^
  --summary "本轮长期有效摘要" ^
  --keywords-json "[\"kw1\",\"kw2\"]"
```

说明：
- `write` 内部最终调用的是 `memorize()`
- 成功后会自动把 `turn` 加 1
- 你不需要自己维护轮次

如果文本很长，推荐用文件：

```cmd
session_cli write --workspace C:\your_project ^
  --question-file C:\tmp\question.txt ^
  --answer-file C:\tmp\answer.txt ^
  --summary-file C:\tmp\summary.txt ^
  --keywords-json "[\"kw1\",\"kw2\"]"
```

### 6.4 归档到长期记忆

```cmd
session_cli flush --workspace C:\your_project
```

作用：
- 把当前 session 的热记忆写入 SQLite
- 清理 Redis 热记忆
- 移除活动会话状态

### 6.5 查看统计

```cmd
session_cli stats --workspace C:\your_project
```

### 6.6 查看当前会话

```cmd
session_cli show --workspace C:\your_project
```

注意：
- `show` 在当前实现里会复用或创建会话状态
- 它不是纯只读探测命令

## 7. 推荐接入方式

### 方式 A：CLI 接入

这是最稳妥的方式，适合外部系统、代理框架、脚本调用。

完整最小流程：

```cmd
session_cli ensure --workspace C:\your_project
session_cli remember --workspace C:\your_project --query "当前问题"
session_cli write --workspace C:\your_project --question "Q" --answer "A" --summary "S"
session_cli flush --workspace C:\your_project
```

### 方式 B：Python API 接入

如果你自己写 Python 应用，可以直接用 API：

```python
import memory_skill_v3 as skill

skill.setup()

memory_text = skill.remember(
    user_id="u1",
    session_id="s1",
    turn=1,
    query_text="用户当前问题",
)

mem_ids = skill.memorize(
    user_id="u1",
    session_id="s1",
    turn=1,
    summary="本轮长期有效摘要",
    keywords=["关键词1", "关键词2"],
    raw_q="用户问题",
    raw_a="AI回答",
)

stats = skill.flush("u1", "s1")
```

### 方式 C：会话封装器

如果你想让流程更省事，可以用 `MemoryChatSession`：

```python
from memory_skill_v3 import MemoryChatSession
```

适合你自己封装 LLM 调用链时使用。

## 8. 记忆内容建议怎么写

推荐保留：
- 用户长期偏好
- 明确约束
- 已确认决定
- 稳定事实
- 能影响后续工作的结论

不要保留：
- 寒暄
- 客套
- 临时状态
- 一次性过程细节
- 纯执行过程描述

好的摘要示例：

```text
用户要求所有脚本兼容 Windows cmd；记忆系统的唯一执行入口固定为 session_cli.py；用户希望 AI 不做健康检查和自测。
```

不好的摘要示例：

```text
今天用户发来一段代码，我看了一下，然后我们聊了几个方向，最后准备后面再说。
```

## 9. 数据库维护命令

这是这次新增的功能。

### 9.1 合并两个 SQLite 记忆库

把 `memory1.db` 合并进 `memory.db`：

```cmd
session_cli merge-db --target-db C:\memory_skill_v3\memory.db --source-db C:\memory_skill_v3\memory1.db
```

行为说明：
- 数据写入 `target`
- `source` 只读
- 如果同一条记录 `id` 相同且内容相同，会跳过
- 如果 `id` 相同但内容不同，会自动重新生成一条新记录 ID 再写入
- 如果来源记录缺失向量，会计入 `missing_embedding`

### 9.2 批量更新 `user_id`

把库内所有 `user_id` 全部改成一个新值：

```cmd
session_cli rewrite-user-id --db-path C:\memory_skill_v3\memory.db --new-user-id my_user
```

如果只想改某个旧值：

```cmd
session_cli rewrite-user-id --db-path C:\memory_skill_v3\memory.db --old-user-id old_user --new-user-id new_user
```

注意：
- 这里改的是 `memories.user_id`
- 不是改每条记忆记录的主键 `memories.id`

## 10. 调试工具

查看 Redis 热记忆和 SQLite 冷记忆：

```cmd
python qry.py
```

它会直接打印：
- Redis 热记忆条数
- SQLite 冷记忆条数
- 每条摘要的简要信息

## 11. 常见问题

### 11.1 `Cannot reach Redis`

说明 Redis 没启动，或者 `MEMORY_REDIS_URL` 配错了。

### 11.2 `Embedding service not reachable`

说明 `MEMORY_EMBED_SERVICE_URL` 指向了一个没启动的服务。

解决方法：
- 启动 `embed_server.py`
- 或者在当前终端执行 `set MEMORY_EMBED_SERVICE_URL=` 切回本地模式

### 11.3 `remember()` 总是空

常见原因：
- 没有长期记忆
- 当前 query 和历史记忆相似度太低
- 你只写了热记忆但还没 `flush`

### 11.4 直接运行 `session_cli` 行不行

可以。

只要 `C:\memory_skill_v3` 在 `PATH` 里，并且系统已经把 Python 脚本关联到命令执行，就可以直接运行：
- `session_cli ...`
- `python session_cli.py ...`
- `python -m memory_skill_v3 ...`

## 12. 当前建议

如果你只是想把这套系统稳定跑起来，建议按下面做：

1. 配好环境变量
2. 启动 Redis
3. 启动 `embed_server.py`
4. 用 `session_cli` 接入，不要一开始就走底层 API
5. 日常对话流程固定成 `ensure -> remember -> write -> flush`

这样最稳，调试成本也最低。
