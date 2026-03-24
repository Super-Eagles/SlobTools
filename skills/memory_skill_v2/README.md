# memory_skill_v2

适用于 AI Agent 的长期记忆技能，支持热记忆（Redis）+ 冷记忆（SQLite + 向量检索）双路存储，自动去重/合并，按 token 预算裁剪后注入提示词。

## 架构

```
memorize()  →  Redis (热记忆, 当前会话)
                    ↓  flush()
              SQLite + sqlite-vec (冷记忆, 持久化)

remember()  →  热记忆 (Redis)  +  冷记忆 (向量检索 + FTS fallback)
                    ↓  inject
              格式化记忆文本块（注入 system prompt）
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动 Redis

- **Windows**：安装 [Memurai](https://www.memurai.com/) 或 [Redis for Windows](https://github.com/microsoftarchive/redis)
- **macOS**：`brew install redis && brew services start redis`
- **Linux**：`sudo apt install redis-server && sudo systemctl start redis`

### 3. 使用示例

```python
import memory_skill_v2 as skill

# 初始化（检查 Redis、SQLite、embedding 模型）
skill.setup()

user_id    = "user_001"
session_id = "session_abc"

# 写入记忆（每轮对话结束后调用）
skill.memorize(
    user_id    = user_id,
    session_id = session_id,
    turn       = 1,
    summary    = "用户想用 Python 构建聊天机器人",
    keywords   = ["Python", "聊天机器人"],
    raw_q      = "我想用 Python 做聊天机器人",
    raw_a      = "推荐使用 LangChain 或 Rasa",
)

# 检索相关记忆（每轮对话开始前调用，注入 system prompt）
context = skill.remember(
    user_id    = user_id,
    session_id = session_id,
    turn       = 2,
    query_text = "有没有更轻量的方案",
)
print(context)   # 将此字符串拼入 system prompt

# 会话结束时持久化到 SQLite
skill.flush(user_id, session_id)
```

### 4. 运行测试

```bash
python -m memory_skill_v2.test_skill
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MEMORY_REDIS_URL` | `redis://localhost:6379` | Redis 连接地址 |
| `MEMORY_SQLITE_PATH` | `./memory.db` | SQLite 数据库路径（相对于 skill 包目录） |
| `MEMORY_EMBED_MODEL` | `paraphrase-multilingual-MiniLM-L12-v2` | sentence-transformers 模型名 |
| `MEMORY_EMBED_DIM` | `384` | 向量维度（须与模型一致） |
| `MEMORY_TOP_K` | `5` | 冷记忆最多返回条数 |
| `MEMORY_SIM_THRESHOLD` | `0.75` | 向量检索相似度下限 |
| `MEMORY_MERGE_THRESHOLD` | `0.88` | 去重合并的相似度上限 |
| `MEMORY_SESSION_TTL` | `86400` | Redis 热记忆过期时间（秒） |

## 注意事项

- **线程安全**：SQLite 连接为单例，内置写锁，可安全用于多线程场景（同一进程内）。  
  跨进程并发写入需改用 WAL 模式或外部锁，当前版本不支持。
- **首次运行**：embedding 模型约 470 MB，会自动下载，请确保网络畅通。
- **中文全文检索**：FTS 查询会自动拆分 CJK 字符为单字 token，无需额外分词工具。
