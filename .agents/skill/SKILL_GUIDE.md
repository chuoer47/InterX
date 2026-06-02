# InterX Skill 编写规范

InterX 项目使用 `.agents/` 目录管理 AI Agent 技能。每个技能定义了一个可重复执行的工作流，由 AI Agent 按步骤执行。

---

## 目录结构

每个技能遵循统一的目录结构：

```
.agents/
├── skill/                          # InterX 公共技能（所有包共享）
│   ├── doc-writer/
│   │   ├── SKILL.md                # 技能定义（必需）
│   │   ├── agents/openai.yaml      # Agent 接口元数据（必需）
│   │   ├── references/             # 参考文档（可选）
│   │   └── scripts/                # 辅助脚本（可选）
│   └── code-comments/
│       └── SKILL.md
└── skills/                         # 包级技能（仅该包使用）
    └── <skill-name>/
        ├── SKILL.md                # 技能定义（必需）
        ├── agents/openai.yaml      # Agent 接口元数据（必需）
        ├── references/             # 参考文档（可选）
        ├── scripts/                # 辅助脚本（可选）
        └── logs/                   # 运行日志（可选，.gitignore）
```

**公共技能 vs 包级技能：**
- `InterX/.agents/skill/` — 所有包共享的技能（如 doc-writer、code-comments）
- `InterX/<package>/.agents/skills/` — 仅该包使用的技能（如 kg-cold-start）

---

## 必需文件

### 1. SKILL.md — 技能定义

这是技能的核心文件，包含 YAML frontmatter 和 Markdown 正文。

**Frontmatter 格式：**

```yaml
---
name: skill-name              # 技能唯一标识（kebab-case）
description: >                # 一句话描述，用于技能选择
  技能的功能描述。当用户要求执行 XXX 时使用本 skill。
---
```

**正文内容应包括：**
1. 技能标题和一句话概述
2. 使用场景（什么时候触发这个技能）
3. 工作流程（分步骤描述 Agent 应该做什么）
4. 输入/输出格式说明
5. 注意事项和约束条件

**示例：**

```markdown
---
name: kg-cold-start
description: >
  从 agentic-rag 证据引用构建知识图谱。
  解析证据、映射行号到 chunk、通过 LLM 提取语义关系、写入 Kùzu 图数据库。
---

# KG 冷启动

从已有的 QA 证据构建知识图谱，无需人工标注。

## 使用场景

当用户要求构建/重建知识图谱时使用本 skill。

## 工作流程

### Phase 1: 解析证据引用
运行 `scripts/resolve_refs.py` ...

### Phase 2: 行号到 Chunk 映射
运行 `scripts/line_to_chunk.py` ...

（以此类推）
```

### 2. agents/openai.yaml — Agent 接口元数据

```yaml
name: skill-name
description: >
  技能的简短描述（1-2 行）。
metadata:
  short-description: 更短的描述
  category: knowledge-graph          # 分类
  tags: [kg, cold-start, evidence]   # 标签
```

**或者使用 interface 格式（更完整）：**

```yaml
interface:
  display_name: "Human Readable Name"
  short_description: "简短描述"
  default_prompt: "默认提示词，用户触发时首先发送"
```

---

## 可选文件

### references/ — 参考文档

存放技能执行时需要参考的文档，如模板、规范、schema 定义等。

```
references/
├── extraction_prompt.md     # LLM 提取 prompt 模板
├── graph_schema.md          # 图谱 schema 定义
└── ocr-patterns.md          # OCR 模式参考
```

### scripts/ — 辅助脚本

存放技能执行过程中调用的 Python/Shell 脚本。技能在 SKILL.md 中指引 Agent 运行这些脚本。

```
scripts/
├── resolve_refs.py          # Phase 1: 解析证据引用
├── line_to_chunk.py         # Phase 2: 行号映射
├── write_graph.py           # Phase 3: 构建图结构
└── extract_semantic.py      # Phase 4: LLM 语义提取
```

### logs/ — 运行日志

Agent 执行过程中产生的日志文件。应在 `.gitignore` 中排除。

```
logs/
├── phase3_batch.log         # 主日志
├── phase3_success.log       # 成功记录
├── phase3_failure.log       # 失败记录
└── phase3_console.log       # 控制台输出
```

---

## 编写原则

### 1. 明确的触发条件

在 `description` 和 SKILL.md 的"使用场景"中清楚说明何时触发此技能。Agent 需要根据这些信息判断是否使用该技能。

### 2. 可执行的工作流程

每个步骤应该是 Agent 可以实际执行的：
- 明确的输入文件路径
- 明确的命令（可直接复制粘贴）
- 明确的输出文件路径
- 验证步骤（检查输出是否符合预期）

### 3. 错误处理指导

在 SKILL.md 中说明常见错误及处理方式：
- API 调用失败时的重试策略
- 文件不存在时的处理
- 输出格式异常时的回退方案

### 4. 参数化

使用变量（如 `{question}`, `{manual_id}`）使技能可复用。变量在 SKILL.md 中定义，Agent 在执行时填入实际值。

### 5. 非破坏性约束

技能不应在未经确认的情况下删除或覆盖重要文件。如需修改，应在 SKILL.md 中明确说明需要用户确认的边界。

---

## 现有技能清单

### InterX 公共技能

| 技能 | 位置 | 用途 |
|------|------|------|
| `doc-writer` | `InterX/.agents/skill/doc-writer/` | 为各子包编写项目文档和技术文档 |
| `code-comments` | `InterX/.agents/skill/code-comments/` | 代码注释规范 |

### 包级技能

| 技能 | 位置 | 用途 |
|------|------|------|
| `kg-cold-start` | `InterX/kg/.agents/skills/kg-cold-start/` | 从证据构建知识图谱（四阶段流水线） |
| `manual-image-text-audit` | `InterX/process/.agents/skills/manual-image-text-audit/` | 手册图片-文本对齐审计与清洗 |
| `answer-agentic-rag` | `InterX/agentic-rag/.agents/skills/answer-agentic-rag/` | 英文批量答题 |
| `answer-ch-agentic-rag` | `InterX/agentic-rag/.agents/skills/answer-ch-agentic-rag/` | 中文批量答题 |
| `manual-embed-qa` | `InterX/optimize/.agents/skills/manual-embed-qa/` | 嵌入质量评估 |

---

## 技能执行模式

技能可以通过两种方式执行：

### 1. AI Agent 交互式执行

用户在对话中要求执行某项任务，Agent 根据 `SKILL.md` 中的描述逐步执行。适用于需要人工确认或调试的场景。

### 2. 脚本批量执行

技能的 `scripts/` 目录下的脚本可以独立运行，适用于批量处理和自动化流水线。

```bash
# 示例：批量运行 kg-cold-start
cd InterX/kg
python .agents/skills/kg-cold-start/scripts/resolve_refs.py
python .agents/skills/kg-cold-start/scripts/line_to_chunk.py
python .agents/skills/kg-cold-start/scripts/write_graph.py build ...
```

---

## 新建技能模板

```bash
# 1. 创建目录结构
mkdir -p InterX/<package>/.agents/skills/<skill-name>/scripts
mkdir -p InterX/<package>/.agents/skills/<skill-name>/references
mkdir -p InterX/<package>/.agents/skills/<skill-name>/agents
mkdir -p InterX/<package>/.agents/skills/<skill-name>/logs

# 2. 创建 SKILL.md
cat > InterX/<package>/.agents/skills/<skill-name>/SKILL.md << 'EOF'
---
name: <skill-name>
description: >
  技能描述。
---

# 技能标题

## 使用场景
...

## 工作流程
### Phase 1: ...
### Phase 2: ...
EOF

# 3. 创建 agents/openai.yaml
cat > InterX/<package>/.agents/skills/<skill-name>/agents/openai.yaml << 'EOF'
name: <skill-name>
description: 技能描述
metadata:
  category: <category>
  tags: [<tag1>, <tag2>]
EOF

# 4. 在包的 .gitignore 中排除日志
echo ".agents/**/logs/" >> InterX/<package>/.gitignore
```
