# Memory Agent Rules

本文件不是给人看的开发文档，而是给 AI 执行记忆流程时使用的操作规程。
目标是让 AI 在每一轮对话中，按固定顺序使用 `memory_skill_v2`：

- 回答前先检索记忆
- 检索结果先综合进回答
- 回答后整理本轮内容
- 将整理结果写入热记忆
- 会话结束时再刷入冷记忆

---

## 1. 基本原则

AI 在使用本记忆库时，必须遵循以下原则：

1. 不要跳过记忆检索步骤。
2. 不要先回答、后检索。
3. 检索到的记忆要自然融入回答，不要直接说“根据我的记忆”。
4. 每轮回答后都要整理并保存记忆，不要只在少数轮次保存。
5. 不要把寒暄、无关废话、一次性临时状态存入长期记忆。
6. 用户明确要求结束、归档、flush 时，才将热记忆刷入冷记忆。

---

## 2. 必须维护的三个标识

AI 在整个对话过程中，必须维护以下三个值：

- `user_id`
  - 同一个用户保持不变
- `session_id`
  - 同一次会话保持不变
- `turn`
  - 从 `1` 开始，每轮对话递增 `1`

这三个值缺一不可。

---

## 3. 每轮对话的标准顺序

每一轮收到用户输入后，必须按下面顺序执行。

### 第一步：检索记忆

调用：

```python
memory_text = remember(user_id, session_id, turn, query_text)
```

说明：

- `query_text` 就是用户当前这一轮输入
- 如果返回空字符串，表示当前没有可用记忆
- 如果返回非空字符串，必须把它作为回答前的背景信息使用

---

### 第二步：综合记忆后再回答

AI 回答时：

- 先结合 `memory_text`
- 再结合当前用户问题
- 输出正式回答

要求：

- 不能生硬复述记忆文本
- 不能直接说“我查到了记忆”
- 要把记忆当作背景常识自然融入回答

---

### 第三步：整理本轮记忆

回答完成后，必须把本轮问答整理成：

- `summary`
- `keywords`

整理目标：

只保留以后仍然有价值的信息，例如：

- 用户长期偏好
- 约束条件
- 已确认决定
- 稳定事实
- 项目结论
- 代码结论

不要保留：

- 寒暄
- 空话
- 一次性过程描述
- 无长期价值的细节

建议整理输出格式：

```json
{
  "summary": "一段可读摘要，可包含多个要点；系统后续会自动拆分成多条记忆。",
  "keywords": ["关键词1", "关键词2", "关键词3"]
}
```

---

### 第四步：写入热记忆

调用：

```python
mem_ids = memorize(
    user_id=user_id,
    session_id=session_id,
    turn=turn,
    summary=summary,
    keywords=keywords,
    raw_q=user_text,
    raw_a=answer_text,
)
```

说明：

- `memorize()` 现在返回的是 `mem_id` 列表，不是单个 `id`
- 内部会先整理拆分，再生成多条热记忆
- 同一轮允许产生多条记忆，不会再互相覆盖

---

### 第五步：递增轮次

当前轮处理完成后：

```python
turn += 1
```

---

## 4. 会话结束时的处理

当用户出现下列意图时，应执行冷记忆固化：

- “结束会话”
- “flush 记忆”
- “归档记忆”
- “保存到长期记忆”

调用：

```python
stats = flush(user_id, session_id)
```

说明：

- `flush()` 会把 Redis 热记忆写入 SQLite 冷记忆
- flush 完成后，该 session 的热记忆会被清空

---

## 5. 推荐执行模板

如果 AI 需要严格按流程执行，可直接按此模板：

```python
memory_text = remember(user_id, session_id, turn, user_text)

answer_text = 结合 memory_text 和 user_text 生成正式回答

summary_pack = {
    "summary": "本轮稳定信息摘要",
    "keywords": ["关键词1", "关键词2"]
}

mem_ids = memorize(
    user_id=user_id,
    session_id=session_id,
    turn=turn,
    summary=summary_pack["summary"],
    keywords=summary_pack["keywords"],
    raw_q=user_text,
    raw_a=answer_text,
)

turn += 1
```

如果用户明确要求结束会话，再执行：

```python
flush(user_id, session_id)
```

---

## 6. 错误处理规则

如果出现以下情况，按下面处理：

### `remember()` 返回空

- 正常回答
- 这一轮仍然要保存记忆

### `memorize()` 失败

- 不影响本轮回答
- 但应记录失败原因

### `flush()` 失败

- 不要丢弃当前会话标识
- 允许后续重试

---

## 7. 当前版本的重要事实

AI 应知道当前 `memory_skill_v2` 已具备以下行为：

1. `memorize()` 会先整理拆分，再写入多条热记忆
2. Redis 热记忆键已带 `item_index`，同一轮多条不会互相覆盖
3. `retrieve()` 和 `flush()` 已按 `turn + item_index` 排序
4. SQLite 冷记忆表已包含 `item_index` 和 `kind`
5. `memorize()` 的返回值是 `mem_id` 列表

---

## 8. 给 AI 的最终执行要求

如果 AI 被要求“使用 memory_skill_v2 记忆”，默认就按以下策略执行：

1. 每轮先 `remember()`
2. 再回答
3. 回答后立刻 `memorize()`
4. 用户明确要求结束时再 `flush()`

除非用户明确禁止，否则不要跳过以上流程。
