# 常见问题定位示例

本文件展示如何根据用户问题，精确定位并读取对应文档内容。

---

## 示例 1：问某个类

**用户**：`Engine 类是做什么的？它有哪些成员变量？`

**执行步骤**：
```bash
# Step 1: 已有 00_AI_CONTEXT.md 的认知（必读，已完成）
# 从中确认 Engine 类在 src/core/engine.h

# Step 2: 在类参考文档中精确定位 Engine 类
grep -n "### 类：\`Engine\`\|^## Engine" \
  {PROJECT_ROOT}/_ai_docs/05_CLASS_REFERENCE.md
# 假设输出：247:### 类：`Engine`

# Step 3: 找到类的结束位置（下一个类的开始）
awk 'NR>247 && /^### 类：/{print NR; exit}' \
  {PROJECT_ROOT}/_ai_docs/05_CLASS_REFERENCE.md
# 假设输出：389

# Step 4: 读取该类的完整描述
sed -n '247,389p' {PROJECT_ROOT}/_ai_docs/05_CLASS_REFERENCE.md
```

**回答模板**：
```
## Engine 类

**文件**：src/core/engine.h / engine.cpp
**职责**：[从文档中提取]
**设计模式**：[如：单例]

**关键成员变量**：
（展示文档中的成员变量表格）

**核心方法**：
（展示文档中的方法列表）

**线程安全**：[从文档中提取]
```

---

## 示例 2：问某个函数的实现

**用户**：`MainWindow::onStartClicked() 里面具体做了什么？`

**执行步骤**：
```bash
# Step 1: 在函数参考文档中定位
grep -n "函数：MainWindow::onStartClicked\|MainWindow::onStartClicked" \
  {PROJECT_ROOT}/_ai_docs/06_FUNCTION_REFERENCE.md | head -5

# Step 2: 读取该函数的完整分析（精确行范围）
# 假设找到行号 512，下一个函数在 601
sed -n '512,601p' {PROJECT_ROOT}/_ai_docs/06_FUNCTION_REFERENCE.md
```

**回答**：直接呈现文档中的逐行分析，保留行号引用和局部变量表。

---

## 示例 3：问某个操作的完整流程

**用户**：`用户点击"开始处理"按钮后，整个流程是什么？`

**执行步骤**：
```bash
# Step 1: 列出数据流文档的所有场景
grep -n "^### 场景" {PROJECT_ROOT}/_ai_docs/07_DATA_FLOW.md
# 找到"用户点击开始处理"或"用户触发核心处理"

# Step 2: 读取该场景
sed -n '65,130p' {PROJECT_ROOT}/_ai_docs/07_DATA_FLOW.md

# Step 3: 补充信号槽细节（可选）
grep -n "onStartClicked\|startBtn.*clicked" \
  {PROJECT_ROOT}/_ai_docs/08_QT_SIGNALS_SLOTS.md
```

---

## 示例 4：问信号连接关系

**用户**：`dataReady 这个信号连接到哪里了？`

**执行步骤**：
```bash
# 直接在信号槽文档中全文搜索
grep -n "dataReady" {PROJECT_ROOT}/_ai_docs/08_QT_SIGNALS_SLOTS.md

# 同时看函数参考中的 emit 位置
grep -n "emit dataReady\|dataReady" \
  {PROJECT_ROOT}/_ai_docs/06_FUNCTION_REFERENCE.md | head -10
```

**回答**：展示 connect 档案（发射方/接收方/连接类型/连接位置）。

---

## 示例 5：排查线程安全问题

**用户**：`m_data 这个成员变量是线程安全的吗？`

**执行步骤**：
```bash
# Step 1: 在类参考中找到 m_data 的定义
grep -n "m_data" {PROJECT_ROOT}/_ai_docs/05_CLASS_REFERENCE.md | head -10

# Step 2: 在线程分析文档中找共享资源分析
grep -n "m_data" {PROJECT_ROOT}/_ai_docs/11_THREADING.md

# Step 3: 在已知问题中确认是否有相关记录
grep -n "m_data" {PROJECT_ROOT}/_ai_docs/12_KNOWN_ISSUES.md
```

---

## 示例 6：查找控件名称

**用户**：`UI 上那个显示进度的控件，objectName 是什么？`

**执行步骤**：
```bash
# 搜索 QProgressBar 类型的控件
grep -n "QProgressBar" {PROJECT_ROOT}/_ai_docs/09_QT_UI_WIDGETS.md

# 或直接搜索可能的名称
grep -n "progress\|Progress" {PROJECT_ROOT}/_ai_docs/09_QT_UI_WIDGETS.md
```

---

## 示例 7：了解内存所有权

**用户**：`Engine 对象是什么时候被释放的？`

**执行步骤**：
```bash
# 在内存生命周期文档中搜索
grep -n "Engine\|m_engine" {PROJECT_ROOT}/_ai_docs/10_MEMORY_LIFECYCLE.md

# 补充：在类参考中找析构函数说明
grep -n "析构\|~.*Engine\|~.*ClassName" \
  {PROJECT_ROOT}/_ai_docs/05_CLASS_REFERENCE.md | head -10
```

---

## 示例 8：查询编译问题

**用户**：`这个项目需要哪些 Qt 模块？怎么编译？`

**执行步骤**：
```bash
cat {PROJECT_ROOT}/_ai_docs/03_BUILD_SYSTEM.md
```

---

## 示例 9：综合性问题（跨多文档）

**用户**：`帮我理解一下 DataModel 这个类，包括它如何与界面交互`

**执行步骤**：
```bash
# Step 1: 类本身的定义
grep -n "DataModel" {PROJECT_ROOT}/_ai_docs/05_CLASS_REFERENCE.md | head -5
sed -n '{start},{end}p' {PROJECT_ROOT}/_ai_docs/05_CLASS_REFERENCE.md

# Step 2: 它参与的信号槽
grep -n "DataModel" {PROJECT_ROOT}/_ai_docs/08_QT_SIGNALS_SLOTS.md

# Step 3: 它在数据流中的位置
grep -n "DataModel" {PROJECT_ROOT}/_ai_docs/07_DATA_FLOW.md

# Step 4: 相关已知问题
grep -n "DataModel" {PROJECT_ROOT}/_ai_docs/12_KNOWN_ISSUES.md
```

**回答**：综合四个文档的信息，给出完整的类分析。
说明来源："以下信息来自 05（类定义）、08（信号槽）和 07（数据流）文档的综合。"

---

## 示例 10：发现文档不完整

**用户**：`DatabaseManager 这个类是怎么实现的？`

**执行步骤**：
```bash
# 搜索文档
grep -n "DatabaseManager" {PROJECT_ROOT}/_ai_docs/05_CLASS_REFERENCE.md
# → 无结果
grep -rn "DatabaseManager" {PROJECT_ROOT}/_ai_docs/
# → 无结果
```

**回答**：
```
文档中未找到 DatabaseManager 类的记录。

可能的原因：
1. 该类在文档生成后才被添加到项目中
2. 文档生成时被排除（如在 build/ 目录下）

建议直接查看源码：
```bash
find {PROJECT_ROOT} -name "*.h" | xargs grep -l "class DatabaseManager"
```

若该类重要，建议重新运行文档生成 skill 以更新文档。
```

---

## 性能优化提示

### 避免的操作
```bash
# ❌ 全量加载超大文档
cat {PROJECT_ROOT}/_ai_docs/06_FUNCTION_REFERENCE.md  # 可能 5000+ 行

# ❌ 用 cat 加载所有文档
cat {PROJECT_ROOT}/_ai_docs/*.md
```

### 推荐的操作
```bash
# ✅ 先获取文档章节目录
grep -n "^### \|^## " {PROJECT_ROOT}/_ai_docs/06_FUNCTION_REFERENCE.md

# ✅ 精确读取目标段落
sed -n '${START},${END}p' {PROJECT_ROOT}/_ai_docs/06_FUNCTION_REFERENCE.md

# ✅ 跨文档关键词搜索
grep -n "keyword" {PROJECT_ROOT}/_ai_docs/05_CLASS_REFERENCE.md \
                  {PROJECT_ROOT}/_ai_docs/08_QT_SIGNALS_SLOTS.md
```
