# memory_skill_v3 · AI 直接执行协议

你已经会使用 `memory_skill_v3`。
不要研究源码，不要阅读其他文档推断用法，不要做健康检查，不要先测试能不能用。
直接按下面的固定协议执行。

## 唯一入口

只使用这一条命令入口：

```cmd
session_cli
```

前提：
- `C:\memory_skill_v3` 已加入 `PATH`
- Python 已正确安装并已加入 `PATH`
- 当前系统已支持直接执行 `session_cli`

禁止改用：
- `setup`
- `show`
- 底层 Python API
- `MemoryChatSession`
- `run_chat_turn()`
- 任何“先检查环境再决定怎么用”的做法

## 会话初始化

同一个 `workspace` 第一次开始对话时，先执行一次：

```cmd
session_cli ensure --workspace "<workspace>"
```

规则：
- 同一项目始终使用同一个 `workspace`
- 不要自行生成 `user_id`
- 不要自行生成 `session_id`
- 不要手动维护 `turn`
- 不要使用 `--reset`，除非用户明确要求开启新会话

## 每轮固定流程

每收到一条用户消息，都严格按下面顺序执行。

### 1. 先检索记忆

```cmd
session_cli remember --workspace "<workspace>" --query "<user_text>"
```

从返回 JSON 中读取：
- `memory_text`
- `turn`

规则：
- `remember` 永远先于回答
- 不要先回答再补检索
- `memory_text` 为空时正常继续

### 2. 把 memory_text 合并进同一条 system prompt

如果 `memory_text` 非空，必须把它和原有 system prompt 合并成一条 system 消息。

禁止：
- 把 `memory_text` 作为第二条 system 消息
- 在回答里说“根据我的记忆”
- 生硬复述记忆文本

### 3. 正式回答用户

回答时把记忆当作背景信息自然融入，不额外解释记忆流程。

### 4. 立即整理本轮摘要

摘要只保留长期有效的信息：
- 用户偏好
- 明确约束
- 已确认决定
- 重要结论
- 稳定事实

不要保留：
- 寒暄
- 客套
- 一次性过程
- 临时状态
- 无长期价值的细节

输出结构必须等价于：

```json
{
  "summary": "长期有效的摘要",
  "keywords": ["关键词1", "关键词2"]
}
```

### 5. 写入热记忆

短文本可直接传参：

```cmd
session_cli write --workspace "<workspace>" --question "<user_text>" --answer "<answer_text>" --summary "<summary_text>" --keywords-json "[\"kw1\",\"kw2\"]"
```

长文本或多行文本优先写入文件后再传：

```cmd
session_cli write --workspace "<workspace>" --question-file "<question_file>" --answer-file "<answer_file>" --summary-file "<summary_file>" --keywords-json "[\"kw1\",\"kw2\"]"
```

从返回 JSON 中读取：
- `next_turn`
- `mem_ids`

规则：
- `write` 每轮都要执行
- `turn` 由 `write` 自动递增
- 不要手动 `turn += 1`

## 会话结束

当用户明确表示结束、归档、保存长期记忆时，执行：

```cmd
session_cli flush --workspace "<workspace>"
```

触发语义包括：
- 结束会话
- flush 记忆
- 归档记忆
- 保存到长期记忆

## 维护命令

以下命令不是每轮流程的一部分。
只有当用户明确要求做数据库维护时才执行。

### 合并数据库

把 `source` 的数据合并进 `target`：

```cmd
session_cli merge-db --target-db "C:\memory_skill_v3\memory.db" --source-db "C:\memory_skill_v3\memory1.db"
```

规则：
- 数据写入 `target`
- `source` 只读
- 相同主键且内容相同会跳过
- 相同主键但内容不同会自动生成新记录 ID 后再写入

### 批量更新 user_id

把库内全部 `user_id` 改成一个新值：

```cmd
session_cli rewrite-user-id --db-path "C:\memory_skill_v3\memory.db" --new-user-id "<new_user_id>"
```

只替换指定旧值时：

```cmd
session_cli rewrite-user-id --db-path "C:\memory_skill_v3\memory.db" --old-user-id "<old_user_id>" --new-user-id "<new_user_id>"
```

## 失败处理

如果命令失败：
- 直接报告原始错误
- 不要追加健康检查
- 不要追加测试
- 不要自行阅读源码排查
- 不要切换到别的实现方式

如果失败的是记忆步骤，但用户仍然需要回答业务问题：
- 正常回答用户问题
- 简短说明记忆步骤失败
- 结束，不继续自我排障

## 明确禁止

禁止做以下事情：
- 运行 `setup` 作为例行检查
- 运行 `show` 作为探测
- 阅读 README、源码或其他文档来分析怎么用
- 自己决定改走 API、CLI、包装器中的另一套方案
- 输出“执行状态尾巴”
- 向用户展示内部链路如 `remember -> answer -> write`
- 因为“谨慎”而先做测试

## 一句话规则

你不是来研究 `memory_skill_v3` 怎么用的。
你已经知道怎么用：`ensure` 一次，然后每轮 `remember -> 回答 -> write`，结束时 `flush`。
