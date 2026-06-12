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
- `D:\soft\SlobTools` 已加入 `PATH`
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
- 同一项目始终使用该项目的绝对路径作为 `workspace`（例如 `C:\my_project`）
- 不要自行生成 `user_id`
- 不要自行生成 `session_id`
- 不要手动维护 `turn`
- 不要使用 `--reset`，除非用户明确要求开启新会话

## 编码规则

`session_cli` 在不同系统/Shell 下运行时，命令行参数存在编码风险：

| 场景 | 风险 |
|------|------|
| Windows CMD（默认 GBK）内联传中文 | `--query`/`--question` 等中文参数可能乱码 |
| PowerShell 传中文 | 通常 UTF-8，但不同版本行为不一致 |
| Linux/macOS Shell | 通常安全，但含特殊字符时仍建议用文件 |

**规则：含非 ASCII 文本（中文、日文等）时，必须用文件传参，不得内联传参。**

文件编码要求：
- 保存为 **UTF-8**（带或不带 BOM 均可）
- `session_cli` 读取文件时自动识别 `UTF-8 / UTF-8-BOM / UTF-16 / GBK`，无需手动指定

内联传参仅适用于纯 ASCII 内容（纯英文关键词等）。

## 每轮固定流程

每收到一条用户消息，都严格按下面顺序执行。

### 1. 先检索记忆

```cmd
session_cli remember --workspace "<workspace>" --query "<user_text>"
```

> **含中文时**：`remember --query` 只支持内联传参，无文件选项。
> - Windows CMD（GBK）下运行时，建议先执行 `chcp 65001` 切换到 UTF-8，再运行命令。
> - PowerShell / Linux / macOS Shell 下通常无需处理。
> - 若乱码仍出现，改用工具的文件写入能力将查询文本先写成 UTF-8 文件，再用文件内容拼接成命令字符串传入。

从返回 JSON 中读取：
- `memory_text`
- `turn`（只用于观察当前轮数，无需手动传给其他命令）

规则：
- `remember` 永远先于回答
- 不要先回答再补检索
- `memory_text` 为空时正常继续

### 2. 将 memory_text 纳入背景上下文

如果 `memory_text` 非空，将其视为已知背景，组织回答时自然使用。

禁止：
- 在回答里说"根据我的记忆"
- 生硬复述记忆文本
- 把 `memory_text` 当作独立块输出给用户
- 额外说明记忆的来源或流程

### 3. 正式回答用户

直接回答用户问题。

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

> **注意：如果本轮对话不包含任何长期有价值的稳定信息（如普通地查看/检查文件、简单问答、闲聊等），请直接将 summary 设为空白，输出 `{"summary":"","keywords":[]}`。记忆系统检测到 summary 为空时会自动跳过写入，避免在数据库中产生无价值的临时过程废话。**

> **注：发现旧记忆错误时（仍属于步骤 4，摘要写完后继续步骤 5）**
>
> 如果确认以前记忆中的某个结论错误：
> - 不要直接假设自己可以修改或删除已有记忆
> - 默认做法是新增一条“纠正记忆”，用新结论覆盖旧结论
> - 新摘要必须明确写出：旧结论错误、正确结论、后续以新结论为准
> - `keywords` 优先复用旧主题关键词，并补充“纠错”“修正”“更正”等词，提高后续 `remember` 命中率
> - 回答用户时按新结论执行，不再沿用旧错误结论
> - 只有当用户明确要求物理修改或删除旧记录时，才进入数据库维护流程；否则不要把“纠错”理解成直接改库
>
> 纠错摘要的推荐写法：
>
> ```json
> {
>   "summary": "关于 <主题>，旧结论“<错误结论>”错误；正确结论是“<新结论>”；后续以“<新结论>”为准。",
>   "keywords": ["<主题>", "纠错", "修正", "<新结论关键词>"]
> }
> ```

### 5. 写入热记忆

短文本可直接传参：

```cmd
session_cli write --workspace "<workspace>" --question "<user_text>" --answer "<answer_text>" --summary "<summary_text>" --keywords-json "kw1,kw2"
```

长文本或多行文本优先写入文件后再传：

```cmd
session_cli write --workspace "<workspace>" --question-file "<question_file>" --answer-file "<answer_file>" --summary-file "<summary_file>" --keywords-json "kw1,kw2"
```

`--keywords-json` 支持两种格式，效果相同：
- 逗号分隔字符串：`"kw1,kw2,kw3"`
- JSON 数组：`'["kw1","kw2","kw3"]'`

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
session_cli merge-db --target-db "D:\soft\SlobTools\SlobMemory\memory.db" --source-db "D:\soft\SlobTools\SlobMemory\memory1.db"
```

规则：
- 数据写入 `target`
- `source` 只读
- 相同主键且内容相同会跳过
- 相同主键但内容不同会自动生成新记录 ID 后再写入

### 批量更新 user_id

把库内全部 `user_id` 改成一个新值：

```cmd
session_cli rewrite-user-id --db-path "D:\soft\SlobTools\SlobMemory\memory.db" --new-user-id "<new_user_id>"
```

只替换指定旧值时：

```cmd
session_cli rewrite-user-id --db-path "D:\soft\SlobTools\SlobMemory\memory.db" --old-user-id "<old_user_id>" --new-user-id "<new_user_id>"
```

## 失败处理

如果命令失败：
- 直接报告原始错误
- 不要追加健康检查
- 不要追加测试
- 不要自行阅读源码排查
- 不要切换到别的实现方式

> **注：记忆命令（`remember` / `write` / `flush`）失败时的特例**
>
> 若失败的是记忆步骤而非业务命令，仍需继续完成业务回答：
> - 正常回答用户问题
> - 简短说明哪个记忆步骤失败
> - 结束，不继续自我排障

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
