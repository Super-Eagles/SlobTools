# 文本与 Excel 工具集使用说明

> 使用脚本读取和写入文件，遇到问题，可修改对应脚本
> 所有脚本在同一目录下(D:\soft\SlobTools)，已配置好关联。
> 如要运行脚本 read_gbk 只需用简化命令 read_gbk
> 如果现有脚本功能不满足，也不要使用python命令，修改脚本满足使用功能，不好修改的也可以新增脚本
> 如果有临时文件，可以放在当前目录的tmp目录下，没有就新建一个，临时文件不要乱放

---

## 文件清单(修改时用，使用时用简化命令)

|         文件         |                          用途                           |
| ------------------- | ------------------------------------------------------ |
| `D:\soft\SlobTools\encoding_utils.py` | 公共编码检测模块（其他脚本自动调用，无需直接使用）          |
| `D:\soft\SlobTools\read_file.py`      | 读取 / 搜索文本文件（自动识别 GBK / UTF-8，推荐使用）     |
| `D:\soft\SlobTools\read_gbk.py`       | 读取 / 搜索文本文件（固定以 GBK 解码，不自动检测编码）     |
| `D:\soft\SlobTools\write_file.py`     | 写入文本文件（自动识别并保持原有编码，推荐使用）            |
| `D:\soft\SlobTools\write_gbk.py`      | 写入文本文件（固定写回 GBK 编码）                         |
| `D:\soft\SlobTools\gbktoutf8.py`      | 批量转换目录：GBK → UTF-8                               |
| `D:\soft\SlobTools\utf8togbk.py`      | 批量转换目录：UTF-8 → GBK                               |
| `D:\soft\SlobTools\read_excel.py`     | 读取 Excel 文件（info / read / cell / formula / search / stats） |
| `D:\soft\SlobTools\write_excel.py`    | 写入 Excel 文件（保留格式和公式）                         |
| `D:\soft\SlobTools\cmp.py`            | 对比两个 Excel 文件的单元格差异（pandas 版）              |
| `D:\soft\SlobTools\cmpexcel.py`       | 对比两个 Excel 文件（openpyxl 版，支持插入/删除行检测）   |
| `D:\soft\SlobTools\db_universal.py`   | 读写 SQL Server 或 Redis 数据库                          |
| `D:\soft\SlobTools\filetree.py`       | 查看指定路径的文件树                                      |
| `D:\soft\SlobTools\count_code_lines.py` | 统计源码行数（代码行 / 注释行 / 空行，按语言分类）       |
| `D:\soft\SlobTools\memory.py`          | AI 记忆系统全局入口（支持 remember / memorize / flush / stats） |

> Windows 简化入口：`read_file`、`filetree`、`write_file`、`count_code_lines` 已提供同名 `.cmd`
> 包装脚本，可直接在 PowerShell / cmd 中使用；等价于调用对应的 `.py` 脚本。

---

## read_file（推荐）

自动检测文件编码（GBK / UTF-8 / ASCII / BOM），统一输出为 UTF-8。
比 `read_gbk` 更智能：支持 `--encoding` 手动指定，并输出检测编码信息。

### 读取

```bash
read_file <文件>                          # 读取全文（自动检测编码）
read_file <文件> --start 10 --end 20      # 指定行范围
read_file <文件> --stats                  # 文件统计（行数、大小、检测编码）
read_file <文件> --out result.txt          # 结果保存到文件
read_file <文件> --encoding gbk            # 手动指定编码（跳过自动检测）
read_file <文件> --encoding utf-8          # 手动指定编码
```

### 搜索

```bash
read_file <文件> --search "关键词"
read_file <文件> --search "关键词" --context 3    # 显示前后 3 行
read_file <文件> --search "\d{4}" --regex         # 正则搜索
read_file <文件> --search "ABC" --case-sensitive  # 区分大小写
```

---

## read_gbk

固定以 GBK 解码文件（若文件带 UTF-8 BOM 则自动用 UTF-8 读取）。
不支持 `--encoding` 参数；如需自动检测编码，请使用 `read_file`。

### 读取

```bash
read_gbk <文件>                           # 读取全文
read_gbk <文件> --start 10 --end 20       # 指定行范围
read_gbk <文件> --stats                   # 文件统计（行数、大小）
read_gbk <文件> --out result.txt           # 结果保存到文件
```

### 搜索

```bash
read_gbk <文件> --search "关键词"
read_gbk <文件> --search "关键词" --context 3    # 显示前后 3 行
read_gbk <文件> --search "\d{4}" --regex         # 正则搜索
read_gbk <文件> --search "ABC" --case-sensitive  # 区分大小写
```

---

## write_file（推荐）

自动检测文件编码并以相同编码写回，保证不破坏原有编码（GBK / UTF-8）。
比 `write_gbk` 更通用：支持 `--encoding` 手动指定编码。
每次写入前自动备份（`.bak`），支持原子写入和写后校验。

### 内容来源（三选一）

```bash
--content "文本"       # 直接传入字符串
--content-file path    # 从 UTF-8 文件读取
# 不传任何参数          # 从 stdin 读取
```

### 六种操作模式

```bash
# append — 追加到末尾
write_file <文件> --mode append --content "新增行"

# insert — 在指定行前插入（--start 为行号，1 = 最前面）
write_file <文件> --mode insert --start 5 --content "插入内容"

# replace — 替换指定行范围
write_file <文件> --mode replace --start 10 --end 15 --content "新内容"

# delete — 删除指定行范围
write_file <文件> --mode delete --start 3 --end 7

# patch — 全局文本替换（支持正则，支持跨行匹配）
write_file <文件> --mode patch --old "旧文本" --new "新文本"
write_file <文件> --mode patch --old "\d+" --new "NUM" --regex
write_file <文件> --mode patch --old "foo" --new "bar" --count 1  # 只替换第一处

# overwrite — 完全覆盖文件
write_file <文件> --mode overwrite --content-file new.txt
```

### 常用选项

```bash
--encoding gbk/utf-8   # 手动指定编码（跳过自动检测）
--dry-run              # 预览，不写入
--diff                 # 显示差异对比
--no-backup            # 不生成备份
--allow-loss           # GBK 文件：允许不支持的字符替换为 ?（默认拒绝）
--create               # 文件不存在时自动创建
```

---

## write_gbk

固定写回 GBK 编码。如需自动保持原编码，请使用 `write_file`。
API 与 `write_file` 完全相同，唯一区别是不支持 `--encoding` 参数。

### 六种操作模式（与 write_file 相同）

```bash
write_gbk <文件> --mode append --content "新增行"
write_gbk <文件> --mode insert --start 5 --content "插入内容"
write_gbk <文件> --mode replace --start 10 --end 15 --content "新内容"
write_gbk <文件> --mode delete --start 3 --end 7
write_gbk <文件> --mode patch --old "旧文本" --new "新文本"
write_gbk <文件> --mode patch --old "\d+" --new "NUM" --regex
write_gbk <文件> --mode overwrite --content-file new.txt
```

### 常用选项

```bash
--dry-run              # 预览，不写入
--diff                 # 显示差异对比
--no-backup            # 不生成备份
--allow-loss           # 允许不支持的字符替换为 ?（默认拒绝）
--create               # 文件不存在时自动创建
```

---

## gbktoutf8

批量将目录下文本文件从 GBK 转换为 UTF-8，非文本文件（按扩展名判断）直接跳过不复制。

```bash
gbktoutf8 <源目录> <目标目录>
gbktoutf8 <源目录> <目标目录> --dry-run          # 预览
gbktoutf8 <源目录> <目标目录> --with-bom         # 输出 UTF-8 文件加 BOM
gbktoutf8 <源目录> <目标目录> --log out.log      # 日志写入文件
gbktoutf8 <源目录> <目标目录> --confidence 0.9   # 提高编码置信度阈值
gbktoutf8 <源目录> <目标目录> --follow-links     # 跟随符号链接
```

**输出状态：** `GBK→UTF8` 成功 / `已UTF-8` 无需转换 / `ASCII` 直接复制 / `跳过` 非文本 / `⚠ 不确定` 需人工核查

> **注意：** 源目录与目标目录不能相同，目标目录也不能是源目录的子目录。

---

## utf8togbk

批量将目录下文本文件从 UTF-8 转换为 GBK，非文本文件直接跳过不复制。

```bash
utf8togbk <源目录> <目标目录>
utf8togbk <源目录> <目标目录> --dry-run     # 预览
utf8togbk <源目录> <目标目录> --strict      # 遇到不可编码字符时报错（默认替换为 ?）
utf8togbk <源目录> <目标目录> --log out.log
utf8togbk <源目录> <目标目录> --follow-links
```

**输出状态：** `UTF8→GBK` 成功 / `已是GBK` 无需转换 / `ASCII` 直接复制 / `跳过` 非文本 / `⚠ 有损转` 含不支持字符（已替换为 `?`）/ `⚠ 不确定` 需人工核查

> **注意：** 源目录与目标目录不能相同，目标目录也不能是源目录的子目录。

---

## read_excel

读取 Excel 文件（`.xlsx` / `.xlsm`），支持多种模式和输出格式。

### 六种模式

```bash
# info — 文件概览（工作表列表、行列数、列名）
read_excel <文件>
read_excel <文件> --mode info

# read — 读取数据
read_excel <文件> --mode read
read_excel <文件> --mode read --sheet Sheet2          # 指定工作表
read_excel <文件> --mode read --sheet 0               # 按 0-based 索引指定工作表
read_excel <文件> --mode read --start 5 --end 20      # 指定数据行范围（不含表头）
read_excel <文件> --mode read --cols 姓名 薪资        # 只读指定列
read_excel <文件> --mode read --limit 10              # 最多输出 10 行

# cell — 读取指定单元格的值
read_excel <文件> --mode cell --cells A1 B3:C5

# formula — 读取单元格原始公式（不计算结果）
read_excel <文件> --mode formula --cells B2:D10

# search — 搜索
read_excel <文件> --mode search --search "张三"
read_excel <文件> --mode search --search "技术部" --col 部门
read_excel <文件> --mode search --search "\d{5}" --regex
read_excel <文件> --mode search --search "ABC" --case-sensitive

# stats — 数值列统计（min / max / 均值 / 求和）
read_excel <文件> --mode stats
read_excel <文件> --mode stats --cols 薪资 利润
```

### 输出格式

```bash
--format table    # 对齐表格（默认）
--format json     # JSON
--format csv      # CSV
--format raw      # Tab 分隔纯数据
--out result.json # 结果保存到文件
```

---

## write_excel

写入 Excel 文件，保留所有未修改单元格的格式与公式。
每次写入前自动备份（`.bak`），原子写入。

### 数据格式（`--data` 支持三种写法）

```bash
--data '[{"姓名":"张三","分数":90}]'   # JSON 对象数组（推荐）
--data '[["张三",90],["李四",85]]'     # JSON 二维数组
--data-file rows.json                  # 从 JSON / CSV 文件读取
```

> 以 `=` 开头的值会被写为 Excel 公式，如 `--cells C1="=SUM(A1:B1)"`

### 十种操作模式

```bash
# set-cell — 写入指定单元格
write_excel <文件> --mode set-cell --cells A1=标题 B2=100 C3="=SUM(A1:B1)"

# append — 追加行
write_excel <文件> --mode append --data '[{"姓名":"张三","分数":90}]'

# insert — 在指定行前插入（--start 为 Excel 行号，含表头）
write_excel <文件> --mode insert --start 3 --data '[["新行",100]]'

# replace — 替换指定行范围
write_excel <文件> --mode replace --start 5 --end 7 --data '[["新内容",200]]'

# delete — 删除指定行
write_excel <文件> --mode delete --start 4
write_excel <文件> --mode delete --start 3 --end 6

# patch — 全局文本替换（支持正则）
write_excel <文件> --mode patch --old "旧文本" --new "新文本"
write_excel <文件> --mode patch --old "v\d+" --new "v2.0" --regex

# set-col — 批量写入整列（{row} 替换为实际行号）
write_excel <文件> --mode set-col --col D --value "固定值"
write_excel <文件> --mode set-col --col E --value "=B{row}*C{row}"

# add-sheet / del-sheet / rename-sheet — 工作表管理
write_excel <文件> --mode add-sheet --sheet-name "汇总"
write_excel <文件> --mode del-sheet --sheet "Sheet3"
write_excel <文件> --mode rename-sheet --sheet "Sheet1" --sheet-name "数据"
```

### 常用选项

```bash
--sheet NAME_OR_INDEX  # 指定操作的工作表（默认第一个）
--dry-run              # 预览，不写入
--no-backup            # 不生成备份
--create               # 文件不存在时自动创建
```

### Excel 行号说明

`--start` / `--end` 使用含表头的 Excel 行号：第 1 行 = 表头，第 2 行 = 第 1 条数据，以此类推。

---

## cmp

使用 pandas 对比两个 Excel 文件的单元格内容，适合结构相同（列名一致）的表格比较。

```bash
cmp 表1.xlsx 表2.xlsx
```

- 输出每个 Sheet 中列名仅存在于单侧、行数不同、单元格值不同的情况
- 显示差异时带有 Excel 坐标（如 `[C3]`）和列名提示
- Sheet 按位置顺序两两对比（第1个 vs 第1个，第2个 vs 第2个……）

---

## cmpexcel

使用 openpyxl + difflib 对比两个 Excel 文件，能识别整行的插入/删除，适合有行变动的情况。

```bash
cmpexcel 表1.xlsx 表2.xlsx
```

- 基于行内容的序列比对，能区分 replace / insert / delete 三种变化类型
- 替换时只显示有差异的列（带 Excel 单元格坐标）
- 插入/删除整行时完整显示该行所有单元格内容

---

## db_universal

读写 SQL Server 或 Redis 数据库。

```bash
db_universal sqlserver --help   # 查看 SQL Server 所有用法
db_universal redis --help       # 查看 Redis 所有用法
```

### SQL Server

连接参数（放在 `sqlserver` 子命令之后、操作子命令之前）：

```bash
-H / --host      主机地址（默认 127.0.0.1）
--port           端口（默认 1433）
-U / --user      用户名（默认 sa）
-P / --password  密码（也可设环境变量 SS_PASSWORD）
-d / --database  数据库名（默认 master）
--trusted        Windows 集成认证（不需要用户名密码）
--encrypt        启用 TLS 加密
--timeout        连接超时秒数（默认 30）
--driver         ODBC 驱动名（默认 "ODBC Driver 17 for SQL Server"）
```

操作子命令：

```bash
# query — 执行任意 SQL
db_universal sqlserver -H host -d mydb query --sql "SELECT TOP 10 * FROM users"
db_universal sqlserver -H host -d mydb query --sql "SELECT * FROM orders" --export out.csv

# tables — 列出所有表
db_universal sqlserver -H host -d mydb tables
db_universal sqlserver -H host -d mydb tables --schema dbo

# columns — 列出指定表的字段
db_universal sqlserver -H host -d mydb columns -t users

# select — 快速查询表数据
db_universal sqlserver -H host -d mydb select -t users -n 20
db_universal sqlserver -H host -d mydb select -t orders --where "status='paid'" --order-by "created_at DESC"
db_universal sqlserver -H host -d mydb select -t users --random -n 5   # 随机抽样
db_universal sqlserver -H host -d mydb select -t users --export out.csv

# distinct — 查看某列的所有不同值及数量
db_universal sqlserver -H host -d mydb distinct -t users --field status

# search — 在表中全字段关键词搜索
db_universal sqlserver -H host -d mydb search -t users --keyword "张三"
```

### Redis

连接参数（放在 `redis` 子命令之后、操作子命令之前）：

```bash
-H / --host      主机地址（默认 127.0.0.1）
--port           端口（默认 6379）
--db             数据库编号（默认 0）
-P / --password  密码（也可设环境变量 REDIS_PASSWORD）
--ssl            启用 TLS/SSL
--timeout        连接超时秒数（默认 10）
```

操作子命令：

```bash
# get — 读取字符串 key
db_universal redis -H host get --key mykey

# set — 写入字符串 key
db_universal redis -H host set --key mykey --value "hello"
db_universal redis -H host set --key mykey --value "hello" --ex 3600   # 设过期秒
db_universal redis -H host set --key mykey --value "x" --nx            # 不存在时才写

# del — 删除一个或多个 key
db_universal redis -H host del --keys key1 key2 key3

# keys — 列出匹配的 key（小数据量时用）
db_universal redis -H host keys --pattern "user:*" --limit 100

# scan — 游标遍历匹配的 key（大数据量时用，不阻塞）
db_universal redis -H host scan --pattern "order:*" --limit 200

# ttl — 查看 key 的剩余过期时间
db_universal redis -H host ttl --key mykey

# type — 查看 key 的数据类型
db_universal redis -H host type --key mykey

# hash — Hash 操作
db_universal redis -H host hash hget --key myhash --field name
db_universal redis -H host hash hset --key myhash --field name --value "张三"

# list — List 操作
db_universal redis -H host list lrange --key mylist --start 0 --stop 9

# set — Set 操作
db_universal redis -H host set smembers --key myset

# zset — Sorted Set 操作
db_universal redis -H host zset zrange --key rank --start 0 --stop 9

# stats — 数据库统计信息
db_universal redis -H host stats

# export — 批量导出 key 到 JSON 文件
db_universal redis -H host export --pattern "user:*" --export users.json --limit 5000

# batch-del — 批量删除匹配的 key
db_universal redis -H host batch-del --pattern "tmp:*"
```

---

## filetree

查看指定路径的文件树（只显示源码和配置文件，自动过滤 node_modules、dist、.git 等目录）。
输出树线固定使用 ASCII（`|--` / `` `--``），避免 Windows 终端编码导致树形符号乱码。

```bash
# 查看当前目录
filetree

# 指定路径
filetree /path/to/your/project

# 限制只看 3 层深
filetree . -d 3

# 结果写入文件（自动去掉颜色）
filetree . -o tree.txt

# 关闭颜色
filetree . --no-color
```

---

## count_code_lines

统计源代码行数，适用于软件著作权申请等场合。支持 30+ 种编程语言，自动区分代码行、注释行和空行。

```bash
# 统计当前目录
count_code_lines

# 统计指定目录
count_code_lines -d /path/to/project

# 只统计 C++ 文件
count_code_lines -d . -e .cpp .h .hpp

# 输出报告到文件
count_code_lines -d . -o report.txt

# 额外排除某些目录（在默认排除列表基础上追加，不会覆盖默认配置）
count_code_lines -d . --exclude-dirs legacy temp

# 列出所有支持的语言及对应扩展名
count_code_lines --list-langs
```

**参数说明：**

```bash
-d / --directory     要统计的根目录（默认当前目录）
-e / --extensions    只统计指定扩展名，如 .cpp .h （不指定则统计所有已知语言）
-o / --output        将报告保存到文件（UTF-8 文本）
--exclude-dirs       额外排除的目录名（追加到默认排除列表）
--list-langs         列出所有支持的语言和扩展名后退出
```

**默认自动排除：** `.git`、`node_modules`、`build`、`dist`、`vendor`、`third_party` 等依赖和构建目录（详见脚本 `DEFAULT_EXCLUDE_DIRS`）。

**输出示例：**

```
代 码 统 计 报 告
======================================================================
【总体统计】
  总文件数:        42 个
  总行数:        8520 行
  代码行:        6200 行 (72.8%)
  注释行:         820 行 (9.6%)
  空行:          1500 行 (17.6%)

【按语言统计】
语言            文件数       总行数       代码行       注释行       空行
----------------------------------------------------------------------
C++                 18       5300         3900          500        900
Python              12       2200         1600          200        400
CMake                4        600          450           80         70
...
```

---

## 备份说明

`write_file`、`write_gbk`、`write_excel` 每次写入前自动在原文件同目录生成备份：

```
原文件名.YYYYMMDD_HHMMSS.bak
```

可用 `--no-backup` 关闭，`--dry-run` 不生成备份也不写入任何内容。

---

## memory (AI 记忆系统)

用于在对话过程中实现长短时记忆的存取和管理。

### 核心功能

```bash
# 检索：获取当前问题相关的历史背景
memory.py remember --user <用户ID> --session <会话ID> --text "问题"

# 存入：将本轮结论存入 Redis 热记忆
memory.py memorize --user <用户ID> --session <会话ID> --summary "摘要" --keywords k1 k2

# 固化：将热记忆刷入 SQLite 持久化（会话结束时使用）
memory.py flush --user <用户ID> --session <会话ID>

# 统计：查看记忆总数
memory.py stats --user <用户ID>
```

### 执行规则

1. **先检索**：每轮对话开始前先 `remember`。
2. **后存档**：每一轮回答后立刻 `memorize` 到热记忆。
3. **终持久**：用户要求存档或归档时执行 `flush`。

## word文档转换
```bash
#!/bin/bash

# ============================================================
# Markdown 与 Word/Excel 互转全攻略 (MarkItDown + Pandoc)
# 适用场景：SIT 测试计划、技术文档、AI 辅助修改
# ============================================================

# 0. 环境准备：防止中文乱码 (Windows 终端必运行)
chcp 65001

# ------------------------------------------------------------
# 第一部分：从 Word/Excel 提取内容 (使用 MarkItDown)
# ------------------------------------------------------------

# 1.1 将 Word 转换为 Markdown (智能保留结构，适合喂给 AI)
markitdown "产品系统集成测试计划(SIT测试计划).docx" -o "task.md"

# 1.2 将 Excel 转换为 Markdown (自动转为 MD 表格)
markitdown "测试用例.xlsx" -o "cases.md"

# 1.3 带有图片的 Word 转换 (自动提取图片)
markitdown "带图文档.docx" -o "doc_with_images.md"


# ------------------------------------------------------------
# 第二部分：样式还原与转换 (使用 Pandoc)
# ------------------------------------------------------------

# 2.1 【核心必杀技】带原版样式还原 (借壳生蛋法)
# 注意：template.docx 是你清空了内容但保留了样式的原版 Word 文件
pandoc "task.md" --reference-doc="template.docx" -o "SIT计划_最终版.docx"

# 2.2 导出为 HTML (再用 Excel 打开可变相转为 xlsx)
pandoc "task.md" -s -o "preview.html"

# 2.3 提取图片并转换
# --extract-media 会把 MD 里的图片存到本地目录，防止 Word 里图片丢失
pandoc "task.md" --reference-doc="template.docx" --extract-media=./media -o "final_with_images.docx"


# ------------------------------------------------------------
# 第三部分：开发者进阶命令
# ------------------------------------------------------------

# 3.1 生成一个 Pandoc 默认样式的参考文档 (用来修改样式起点)
pandoc --print-default-data-file reference.docx > my_style_basis.docx

# 3.2 批量转换当前目录下所有 MD 文件为 Word
for f in *.md; do
    pandoc "$f" --reference-doc="template.docx" -o "${f%.md}.docx"
done

# 3.3 转换 Markdown 表格为 CSV (适合导入数据库或极简 Excel)
pandoc "task.md" -t csv -o "data_only.csv"

echo "所有操作示例已列出。请确保 template.docx 存在于当前目录。"
```

