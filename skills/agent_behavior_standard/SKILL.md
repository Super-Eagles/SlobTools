---
name: agent_behavior_standard
description: AI 行为准则，用于规范 AI 在当前环境下的操作行为，防止常见 Bug 和逻辑循环。
---

# AI 行为准则 (Agent Behavior Standard)

为了确保每一轮对话的高效、清醒，AI 在启动时必须遵循以下契约：

## 1. 记忆资产契约 (Memory Assets)
- **唯一路径**：操作记忆必须仅使用全局命令 `memory`。
- **禁止行为**：严禁在 `tmp` 目录下生成临时的 Python 记忆脚本。
- **标准流程**：回答前 `memory remember` -> 回答后 `memory memorize` -> 必要时 `memory flush`。

## 2. Windows 环境契约 (Windows Environment)
- **路径规范**：在处理文件时，一律使用绝对路径。
- **编码强制**：读取 `.h`, `.cpp`, `.txt` 等文本时，如遇乱码报错，必须尝试 `GBK` (Encoding default) 编码读取。
- **工具优先**：优先使用 `D:\soft\SlobTools\Tools.md` 中列出的成熟脚本，而非自行编写临时 Python 代码。
- **进化原则**：如果现有工具功能不满足需求（如缺少参数、逻辑有误），**严禁绕过工具**，必须直接修改原脚本进行“改造”或新增脚本，并同步更新 `Tools.md`。


- **全自动执行合约**：如果用户在对话中提到关键字“全自动”、“全速执行”或“/turbo”，AI 在接下来的任务中，涉及 `run_command` 的指令必须将 `SafeToAutoRun` 设为 `true`，以跳过用户手动确认。

## 3. 防循环契约 (Anti-Loop)
- **禁止复读**：严禁在回答中出现类似 "Step Id: XXX Go" 的内部调试性文字。
- **简洁逻辑**：如果一个任务需要超过 3 步操作，每一步完成后必须验证结果，严禁“盲目快进”。

## 4. 纠错契约 (Error Correction)
- **承认失败**：如果工具调用连续 2 次失败，必须向用户如实报告，不得强行尝试第 3 次。
- **禁止幻觉**：对于不确定的系统变量或库函数，必须先搜索再下结论。

---
*注：本准则优先于 AI 的通用习惯。若指令冲突，以此准则为准。*
