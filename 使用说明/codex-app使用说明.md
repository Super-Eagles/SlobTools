# Codex App 完整使用手册

> 基于 OpenAI 官方文档整理，适用于 Codex App、CLI 及 IDE Extension。
> 官方文档地址：https://developers.openai.com/codex

---

## 目录

1. [什么是 Codex](#1-什么是-codex)
2. [安装与登录](#2-安装与登录)
3. [项目管理](#3-项目管理)
4. [发起任务与对话](#4-发起任务与对话)
5. [Review 代码审查](#5-review-代码审查)
6. [Worktrees 工作树](#6-worktrees-工作树)
7. [Automations 自动化](#7-automations-自动化)
8. [Local Environments 本地环境](#8-local-environments-本地环境)
9. [Skills 技能](#9-skills-技能)
10. [AGENTS.md 持久指令](#10-agentsmd-持久指令)
11. [MCP 集成](#11-mcp-集成)
12. [配置文件 config.toml](#12-配置文件-configtoml)
13. [沙盒与权限控制](#13-沙盒与权限控制)
14. [App 设置详解](#14-app-设置详解)
15. [Web 搜索](#15-web-搜索)
16. [快捷键与斜杠命令](#16-快捷键与斜杠命令)
17. [最佳实践](#17-最佳实践)
18. [常见问题排查](#18-常见问题排查)

---

## 1. 什么是 Codex

Codex 是 OpenAI 的编程智能体，能够读取、编辑和运行代码。它可以：

- 编写新功能和修复 Bug
- 运行测试、Lint、构建等命令
- 审查代码，识别潜在问题
- 并行处理多个任务（通过 Worktrees）
- 通过 Automations 在后台定期执行例行任务

**Codex 有三种使用方式，共享配置：**

| 方式 | 适合场景 |
|------|---------|
| **Codex App**（桌面应用） | 多任务并行、完整 Git 工作流 |
| **IDE Extension** | 在编辑器内实时聊天和改代码 |
| **CLI** | 终端用户、脚本化、自动化 |

**支持的计划：** ChatGPT Plus、Pro、Business、Edu、Enterprise。

---

## 2. 安装与登录

### 下载安装

- **macOS（Apple Silicon）**：从官网下载 .dmg 安装包
- **Windows**：下载 Windows 安装包，原生运行于 PowerShell，不需要 WSL

### 登录方式

打开 Codex App 后选择登录方式：

- **ChatGPT 账号**（推荐）：支持云端线程等完整功能
- **OpenAI API Key**：可用，但云端线程等部分功能不可用

---

## 3. 项目管理

### 创建项目

启动后选择一个本地文件夹作为项目根目录。之前用过 CLI 或 IDE Extension 的项目会自动出现在列表中。

### 项目拆分原则

如果一个仓库包含多个独立应用或模块（如前后端分离），建议为每个模块创建独立的 App 项目，让沙盒只包含对应的文件范围。

### 多项目并行

一个 Codex App 窗口可以管理多个项目，通过侧边栏切换。每个项目有独立的线程历史、设置和沙盒环境。

### 本地 vs 云端模式

发送第一条消息前，选择运行模式：

- **Local**：在本机运行，适合需要即时反馈的任务
- **Cloud**：在 OpenAI 云端环境运行，可后台并行，适合耗时任务

---

## 4. 发起任务与对话

### 基本使用

选择项目后，在 Composer（输入框）输入任务描述，Codex 会自动读取文件、执行命令并展示结果。

### 图片输入

将图片拖入 Composer 即可作为上下文；按住 `Shift` 拖入可将图片添加到上下文列表中。

### 语音输入

按住 `Ctrl+M`（Composer 可见时）开始说话，语音会自动转写。可以编辑转写结果后再发送。

### 浮出对话窗

可将当前活跃线程弹出为独立窗口，方便放置在浏览器、编辑器或设计稿旁边同时工作。勾选"置顶"选项让窗口保持在最前。

### 上下文引用

- 在 CLI/IDE 中使用 `@文件路径` 引用文件
- 输入 `$` 可触发 skill 提及
- 使用 `/mention` 斜杠命令添加文件到上下文

### 一个任务 = 一个线程

不要在一个线程里混杂多个无关任务。每个独立任务开一个新线程，保持上下文干净。

---

## 5. Review 代码审查

Review 面板用于查看 Codex 的修改、给出反馈，并决定提交哪些内容。

> 仅适用于已纳入 Git 仓库的项目。

### 面板视图模式

| 模式 | 说明 |
|------|------|
| **Unstaged / Staged** | 未暂存 / 已暂存的变更 |
| **All branch changes** | 与 base branch 的完整 diff |
| **Last turn changes** | 只看最近一轮的修改 |

### 内联评论

在 diff 的某一行悬停，点击 `+` 按钮即可添加内联评论。评论会锚定到对应行，Codex 回复时精准度更高。

评论完成后，发一条消息明确意图，例如："处理内联评论，保持修改范围最小。"

### Git 操作

Review 面板内支持：

- Stage / Unstage 单个文件或全部变更
- Revert 单个文件或全部变更
- Commit（无需离开 App）

### `/review` 斜杠命令

在线程中使用 `/review` 触发代码审查流程，评论会直接显示在 Review 面板的对应行上。

如果项目中有 `code_review.md` 并在 `AGENTS.md` 中引用，Codex 会按照其中的审查标准执行，实现团队级别的一致性。

---

## 6. Worktrees 工作树

Worktree 让 Codex 在同一个项目中并行运行多个独立任务，互不干扰。

> 仅适用于 Git 仓库项目。

### 类型

| 类型 | 说明 |
|------|------|
| **Codex-managed worktree** | 轻量、临时，每个线程独占，默认保留最近 15 个 |
| **Permanent worktree** | 长期存在，可供多个线程使用，不自动删除 |

### 创建永久 Worktree

从侧边栏项目的三点菜单中选择"创建永久 Worktree"，它会作为独立项目出现在侧边栏。

### Handoff（切换环境）

通过线程头部的"Hand off"按钮，可以将当前线程在 Local 和 Worktree 之间切换，Codex 会自动处理 Git 操作。

### 存储位置与恢复

Worktree 存储在 `$CODEX_HOME/worktrees`。删除 Codex-managed worktree 前，Codex 会保存快照；重新打开该线程时可以选择恢复。

### 自动删除设置

默认保留最近 15 个。可在设置中修改保留数量，或关闭自动删除。

---

## 7. Automations 自动化

Automations 让 Codex 按计划在后台定期执行任务，无需人工触发。

### 创建 Automation

1. 在侧边栏打开 Automations 面板
2. 设置任务描述（prompt）
3. 设置执行频率（如每天、每小时）
4. 选择运行位置：Local 项目目录 或 Worktree（推荐）
5. 可选：指定模型和推理强度

### Inbox（收件箱）

所有 Automation 运行结果统一显示在"Triage"区域。有发现（findings）的运行会出现在 Inbox；无需关注的结果自动归档。支持过滤"全部运行"或"仅未读"。

### 最佳实践

- **先手动测试**：正式排期前，先在普通线程里测试同样的 prompt，确认结果符合预期
- **用 Skill 封装逻辑**：用 `$skill-name` 在 automation 中调用，便于维护和团队共享
- **定期归档**：不再需要的 run 及时归档，避免 Worktree 堆积

### 沙盒注意事项

| 沙盒模式 | Automation 风险 |
|---------|----------------|
| read-only | 工具调用会失败（无法写文件） |
| workspace-write（推荐） | 只能修改工作区内文件 |
| full access | 高风险，Codex 可不受限制修改文件、访问网络 |

---

## 8. Local Environments 本地环境

用于配置 Worktree 创建时的自动化安装步骤和常用操作。

### Setup Script（安装脚本）

每次创建新 Worktree 时自动执行，用于安装依赖或构建项目。

```bash
# TypeScript 项目示例
npm install
npm run build
```

可以为不同平台指定不同脚本（macOS / Windows / Linux）。

> **注意**：Setup Script 运行在独立的 Bash session 中，`export` 命令不会持久到 agent 阶段。如需持久化环境变量，添加到 `~/.bashrc` 或在环境变量设置里配置。

### Actions（快捷操作）

在 App 顶部工具栏定义常用操作，如"启动开发服务器"或"运行测试"，点击即可在集成终端中执行。

---

## 9. Skills 技能

Skill 是一段可复用的工作流指令，由 `SKILL.md` 文件加上可选脚本和资源组成。

### 核心原理：渐进式披露

Codex 启动时只加载 skill 的元数据（名称 + 描述），只有真正需要时才读取完整 `SKILL.md`，节省 token 消耗。

### Skill 目录结构

```
my-skill/
├── SKILL.md              # 必须，包含 name 和 description
├── agents/
│   └── openai.yaml       # 可选，配置调用策略和 UI 元数据
└── scripts/              # 可选，Codex 调用的 CLI 脚本
```

### SKILL.md 基本格式

```markdown
---
name: commit
description: >
  将修改按语义分组后提交。当用户想提交、整理 commit 或
  在推送前清理分支时使用。
---

## 步骤

1. 运行 `git diff --staged` 检查已暂存的变更
2. 按功能模块分组，生成符合约定式提交规范的 commit message
3. 执行 `git commit`
```

### agents/openai.yaml 配置

```yaml
interface:
  display_name: "语义化提交"
  short_description: "按语义分组提交代码修改"
  icon_small: "./assets/icon.svg"
  brand_color: "#3B82F6"
  default_prompt: "帮我整理并提交当前修改"

policy:
  allow_implicit_invocation: true   # false 则只响应显式 $skill 调用

dependencies:
  tools:
    - type: "mcp"
      value: "github"
      description: "GitHub MCP server"
      transport: "streamable_http"
      url: "https://mcp.github.com"
```

### Skill 安装位置

| 范围 | 路径 | 适用场景 |
|------|------|---------|
| 全局（个人） | `~/.codex/skills/my-skill/` | 所有仓库可用 |
| 项目（团队） | `.agents/skills/my-skill/` | 提交到仓库，团队共享 |

### 在 config.toml 中注册 Skill

```toml
[[skills.config]]
path = "/path/to/skill/SKILL.md"
# enabled = false  # 临时禁用
```

修改后需重启 Codex 生效。

### 调用 Skill

- **显式调用**：在 prompt 中输入 `$skill-name`，或 CLI 中输入 `/skills` 查看列表
- **隐式调用**：Codex 根据任务描述自动匹配，前提是 `allow_implicit_invocation: true`

### 每次对话自动加载 Skill

在 `~/.codex/AGENTS.md` 中添加强制规则：

```markdown
## 全局规则
- 每次新对话开始时，调用 $my-skill 加载工作规范。
```

---

## 10. AGENTS.md 持久指令

`AGENTS.md` 是 Codex 的"永久记忆"，每次启动时自动加载，无需在每条 prompt 中重复说明。

### 文件层级与优先级

| 级别 | 路径 | 说明 |
|------|------|------|
| 全局 | `~/.codex/AGENTS.md` | 个人默认，适用所有仓库 |
| 仓库级 | `<项目根目录>/AGENTS.md` | 团队共享规范 |
| 子目录级 | `<子目录>/AGENTS.md` | 局部覆盖，优先级最高 |

**合并规则**：从根目录向下拼接，靠近当前目录的文件优先级更高。默认最大合并大小为 32 KiB。

### 典型内容示例

```markdown
# ~/.codex/AGENTS.md

## 工作约定
- 修改 JavaScript 文件后必须运行 `npm test`。
- 安装依赖优先使用 `pnpm`。
- 新增生产依赖前请确认。

## 提交规范
- 遵循约定式提交（Conventional Commits）。
- 提交信息使用中文。

## 代码风格
- 函数优先使用箭头函数。
- 使用 TypeScript 严格模式。
```

### 初始化命令（CLI）

```bash
codex /init
```

在当前目录生成初始 `AGENTS.md`，建议修改以匹配团队实际规范。

### App 内自定义指令

Settings → Personality → 自定义指令，修改会同步写入个人 `~/.codex/AGENTS.md`。

---

## 11. MCP 集成

MCP（Model Context Protocol）用于将 Codex 连接到外部工具和数据源，如 GitHub、Figma、Linear、浏览器等。

### 添加 MCP Server

**方式一：App 内操作**

Settings → MCP servers → 启用推荐 server 或添加自定义 server

**方式二：CLI 命令**

```bash
# 添加 stdio 类型 server
codex mcp add context7 -- npx -y @upstash/context7-mcp

# 添加 HTTP 类型 server（带 bearer token）
codex mcp add my-server --env TOKEN=xxx --http https://my-server.example.com/mcp

# 查看已配置的 server
codex mcp list

# 在 CLI TUI 中查看活跃 server
/mcp
```

**方式三：直接编辑 config.toml**

```toml
# stdio server 示例
[mcp_servers.context7]
command = "npx"
args = ["-y", "@upstash/context7-mcp"]

# HTTP server 示例
[mcp_servers.my-server]
url = "https://my-server.example.com/mcp"
bearer_token_env_var = "MY_TOKEN"
```

### 配置共享

App、CLI、IDE Extension 共享同一个 MCP 配置（`~/.codex/config.toml`），在任意一处配置后，其他客户端自动生效。

### 项目级 MCP

在项目目录下创建 `.codex/config.toml`（需标记为 trusted 项目）可配置项目专属的 MCP server。

---

## 12. 配置文件 config.toml

### 文件位置与优先级（从高到低）

1. 命令行参数 `-c key=value`
2. 项目配置 `.codex/config.toml`（trusted 项目）
3. 用户配置 `~/.codex/config.toml`
4. 系统配置
5. 内置默认值

### 常用配置项

```toml
# 默认模型
model = "gpt-5-codex"

# 推理强度：low / medium / high
reasoning_effort = "medium"

# 对话风格：friendly / pragmatic / none
personality = "pragmatic"

# 权限策略：on-request / never / untrusted
approval_policy = "on-request"

# 沙盒模式：read-only / workspace-write / full-access
sandbox_mode = "workspace-write"

# Web 搜索：cached / live / disabled
web_search = "cached"

# Windows 沙盒（Windows 专用）
[windows]
sandbox = "elevated"
```

### 多 Profile 配置

```toml
# 定义一个"严格安全"profile
[profiles.strict]
approval_policy = "untrusted"
sandbox_mode = "workspace-write"
```

切换 profile：

```bash
codex --profile strict
```

### 高级沙盒配置

```toml
approval_policy = "untrusted"
sandbox_mode = "workspace-write"
allow_login_shell = false

# 精细化审批策略示例
# approval_policy = { granular = {
#   sandbox_approval = true,
#   rules = true,
#   mcp_elicitations = true,
#   request_permissions = false,
#   skill_approval = false
# } }

[sandbox_workspace_write]
exclude_tmpdir_env_var = false
exclude_slash_tmp = false
writable_roots = ["/Users/you/.pyenv/shims"]
network_access = false
```

---

## 13. 沙盒与权限控制

### 沙盒模式对比

| 模式 | 文件访问 | 网络访问 | 适用场景 |
|------|---------|---------|---------|
| `read-only` | 只读 | 无 | 只需查阅代码 |
| `workspace-write`（推荐） | 只能写工作区 | 无（可选开启） | 日常开发 |
| `full-access` / `--yolo` | 不受限 | 不受限 | 外部加固环境专用 |

### 授权提示

当 Codex 需要执行命令时，会弹出授权提示：

- **Approve once**：只批准这一次
- **Approve for this session**：本次会话内批准
- **自动规则（Rules）**：在 `AGENTS.md` 或 config 中预设白名单，避免重复弹窗

### Rules 命令白名单

在 `~/.codex/AGENTS.md` 中声明允许不经询问直接运行的命令：

```markdown
## 允许自动执行
- npm test
- npm run lint
- git status
- git diff
```

---

## 14. App 设置详解

打开方式：菜单栏 → Settings，或快捷键 `Cmd+,`

### General（通用）

| 设置项 | 说明 |
|-------|------|
| 文件打开方式 | 选择默认编辑器（VS Code、Cursor 等） |
| 命令输出截断 | 控制线程中显示多少命令输出 |
| 多行发送快捷键 | 开启后需 `Cmd+Enter` 发送，`Enter` 换行 |
| 运行时防止休眠 | 长任务运行时保持机器不睡眠 |

### Notifications（通知）

- 永不发送通知
- 始终发送（包括 App 在前台时）
- 自定义：仅在 App 不在前台时通知

### Appearance（外观）

- 主题：亮色 / 暗色 / 系统
- 自定义强调色、背景色、前景色
- UI 字体 / 代码字体
- 支持将自定义主题分享给他人

### Git 设置

- 自定义分支命名规则
- 是否使用 Force Push
- 自定义 commit message 生成提示词
- 自定义 PR 描述生成提示词

### MCP 服务器

- 启用推荐 server（自动处理 OAuth）
- 添加自定义 server
- 此处配置同时对 CLI 和 IDE Extension 生效

### Personality（个性风格）

- **Friendly**：亲切友好
- **Pragmatic**：简洁务实
- **None**：关闭人格化指令

自定义指令会写入 `~/.codex/AGENTS.md`。

### 归档线程

Settings 底部的"Archived threads"列出所有归档的对话，包含日期和项目上下文。

---

## 15. Web 搜索

Codex 内置 Web 搜索工具，本地任务默认开启。

### 搜索模式

| 模式 | 说明 | 安全性 |
|------|------|-------|
| `cached`（默认） | 从 OpenAI 维护的索引返回结果 | 较高（减少实时注入风险） |
| `live` | 实时抓取最新网页 | 适合需要最新数据的任务 |
| `disabled` | 完全关闭 | 最高 |

在 `config.toml` 中配置：

```toml
web_search = "cached"
# web_search = "live"
# web_search = "disabled"
```

使用 `--yolo` 或 full access 沙盒时，默认使用 `live` 模式。

---

## 16. 快捷键与斜杠命令

### App 快捷键

| 快捷键 | 功能 |
|-------|------|
| `Cmd+,` | 打开设置 |
| `Cmd+K` | 打开命令面板 |
| `Ctrl+L` | 清除终端 |
| `Ctrl+M` | 语音输入（按住说话） |

### 斜杠命令（CLI / App 通用）

| 命令 | 说明 |
|------|------|
| `/init` | 在当前目录生成初始 AGENTS.md |
| `/review` | 启动代码审查流程 |
| `/compact` | 压缩对话历史，减少 token 消耗 |
| `/skills` | 查看可用 skill 列表 |
| `/mcp` | 查看活跃的 MCP server |
| `/mention` | 将文件添加到上下文 |
| `/experimental` | 切换实验性功能 |
| `/personality` | 临时切换 Codex 风格 |
| `$skill-name` | 显式调用指定 skill |

---

## 17. 最佳实践

### 提示词策略

- 提供充足上下文（相关文件路径、错误信息、预期行为）
- 复杂任务先让 Codex 制定计划，再逐步执行
- 长任务拆分为里程碑，每个里程碑在新的云端线程中执行
- 不要在 prompt 中堆砌永久性规则，将其移入 `AGENTS.md` 或 Skill

### 效率习惯

- 每个任务独立一个线程（不要混用）
- 多任务并行：多个线程同时运行，不要依次等待
- 在 `AGENTS.md` 中告知 Codex 如何运行 build 和 test 命令
- 任务进行中可以继续自己的工作，无需盯着看

### 分层配置体系

```
~/.codex/AGENTS.md             → 个人全局规范
~/.codex/config.toml           → 全局配置（模型、沙盒、MCP）
~/.codex/skills/               → 个人全局 skill

<项目根>/.codex/config.toml    → 项目级配置（trusted 项目）
<项目根>/AGENTS.md             → 仓库级指令（提交到 Git）
<项目根>/.agents/skills/       → 仓库级 skill（团队共享）

<子目录>/AGENTS.md             → 模块级指令（最高优先级）
```

### Skills 使用原则

- 每个 skill 只做一件事
- description 写清楚"做什么"和"何时触发"
- 从 2–3 个典型用例开始，再逐步扩展
- 可复用的流程 → Skill；重复的日程任务 → Automation

### MCP 连接原则

- 只连接能真正解锁工作流的 server
- 先从 1–2 个最常用的工具开始
- Skills + MCP 组合使用效果最佳

### 常见反模式（避免）

- 把永久规则堆在每次 prompt 里，而不是写进 AGENTS.md
- 不告诉 Codex 如何运行 build 和 test 命令
- 一个项目只用一个线程处理所有任务
- 每步都盯着 Codex，而不是并行做自己的工作

---

## 18. 常见问题排查

### Skill 未被触发

1. 检查 `SKILL.md` 是否包含 `name` 和 `description`
2. 确认 skill 已在 `config.toml` 中注册，或位于正确目录
3. 检查 `allow_implicit_invocation` 是否被设为 `false`
4. 重启 Codex，让其重新扫描 skill 列表
5. 运行 `echo $CODEX_HOME` 确认 home 目录路径正确

### AGENTS.md 不生效

- 确认文件路径是 `~/.codex/AGENTS.md`（全局）或项目根目录下
- 检查项目是否被标记为 `untrusted`（untrusted 项目跳过项目级配置）
- 检查合并后文件是否超出 32 KiB 限制

### 沙盒权限错误

- Automation 在 read-only 沙盒下失败 → 将沙盒改为 `workspace-write`
- 命令需要写工作区外的文件 → 在 Rules 中添加白名单或切换沙盒模式

### Worktree 磁盘占用过大

- 将自动保留数量调小（默认 15）
- 定期归档 Automation 运行记录
- 避免高频 Automation 使用 Worktree 模式

### MCP Server 连接失败

- 检查 `config.toml` 中 command / url 是否正确
- 对于 OAuth 类型 server，重新在 App 中完成授权流程
- 检查 `bearer_token_env_var` 对应的环境变量是否已设置

---

*文档整理自 https://developers.openai.com/codex，如需查阅最新信息请访问官方文档。*
