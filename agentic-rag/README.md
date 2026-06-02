# InterX Agentic RAG

产品手册问答评估数据集 — 中英文双语问答基准与证据追溯。

## 项目概述

`agentic-rag` 是 InterX 系统的**问答评估数据集（Benchmark）**，不是代码包。它包含基于产品手册构建的中英文问答对、人工审核的证据笔记、以及由 agentic RAG 管道生成的答案。

该数据集用于评估 InterX 问答系统的准确性、证据可追溯性和图片引用质量。每个问题都标注了来源手册、证据行号和关联图片，支持端到端的答案质量验证。

同时该数据集用于冷启动知识图谱。

## 数据规模

| 指标 | 中文（ch） | 英文（en） | 合计 |
|------|-----------|-----------|------|
| 问题数 | 163 | 188 | 351 |
| 产品手册 | 21 | 21 | 42 |
| 证据笔记 | 163 | 187 | 350 |
| 逐题答案 | 163 | 187 | 350 |
| 手册插图 | 2,631 | 2,631 | 5,262 |

## 项目结构

```
agentic-rag/
├── ch-question.csv                 # 中文问题集（id, raw, clean, lang）
├── en-question.csv                 # 英文问题集
├── ch-todo.csv                     # 中文答题追踪（状态、手册猜测、证据状态）
├── en-todo.csv                     # 英文答题追踪
├── ch-manual/                      # 中文产品手册（21 份 Markdown）
│   ├── 手册内容总览.md              # 手册索引与路由指南
│   ├── 冰箱手册.md
│   ├── 吹风机手册.md
│   ├── ...
│   └── 插图/                       # 手册引用图片（2,631 张）
├── en-manual/                      # 英文产品手册（21 份 Markdown）
│   ├── 手册内容总览.md
│   ├── Bosch Microwave.md
│   ├── Canon EOS 20D.md
│   ├── ...
│   └── 插图/                       # 手册引用图片（2,631 张）
├── answers/
│   ├── ch-answers/
│   │   ├── ch-answers.csv          # 中文答案汇总（id, ret）
│   │   ├── ch-answers.jsonl        # 中文答案 JSON Lines 格式
│   │   ├── evidence-notes/         # 每题的证据笔记（163 个 .md 文件）
│   │   │   ├── 64.md
│   │   │   ├── 65.md
│   │   │   └── ...
│   │   └── per_question/           # 每题的结构化答案（163 个 .json 文件）
│   │       ├── 64.json
│   │       ├── 65.json
│   │       └── ...
│   └── en-answers/
│       ├── en-answers.csv
│       ├── en-answers.jsonl
│       ├── evidence-notes/         # 英文证据笔记（187 个 .md 文件）
│       └── per_question/           # 英文逐题答案（187 个 .json 文件）
└── .agents/                        # Agentic RAG 技能定义与脚本
    ├── answer-agentic-rag-prd.md
    ├── answer-ch-agentic-rag-prd.md
    ├── scripts/                    # 批量运行与同步脚本
    └── skills/                     # 技能定义（answer-agentic-rag, answer-ch-agentic-rag）
```

## 数据格式

### 问题集（ch-question.csv / en-question.csv）

| 字段 | 说明 |
|------|------|
| `id` | 问题唯一 ID |
| `raw` | 原始问题文本 |
| `clean` | 清洗后的问题文本 |
| `lang` | 语言标记（`zh` / `en`） |

### 答题追踪（ch-todo.csv / en-todo.csv）

| 字段 | 说明 |
|------|------|
| `id` | 问题 ID |
| `question` | 问题文本 |
| `status` | 答题状态（`done` / 其他） |
| `manual_guess` | 路由到的目标手册 |
| `evidence_status` | 证据审核状态（`checked`） |
| `answer_path` | 答案文件路径 |
| `image_ids` | 引用的图片 ID 列表 |
| `notes` | 答题备注（含证据说明和图片验证） |
| `updated_at` | 更新时间 |

### 逐题答案（per_question/*.json）

```json
{
  "id": "100",
  "question": "使用洗碗机前如何安装可折叠下层篮架？",
  "content": "可折叠下层篮架丝已安装在洗碗机下层碗篮上，无需单独安装。<PIC>",
  "images": ["Manual06_13"],
  "evidence_refs": [
    {
      "file": "agentic-rag/ch-manual/洗碗机手册.md",
      "lines": "290-292",
      "text": "可折叠下层篮架丝已安装在机器下层碗篮上..."
    }
  ],
  "status": "answered",
  "notes": "已使用洗碗机手册证据作答..."
}
```

| 字段 | 说明 |
|------|------|
| `content` | 答案正文，`<PIC>` 为图片占位符 |
| `images` | 图片 ID 列表，与 `<PIC>` 按顺序对应 |
| `evidence_refs` | 证据来源（文件路径 + 行号 + 原文摘录） |
| `status` | 答案状态 |
| `notes` | 生成备注 |

### 证据笔记（evidence-notes/*.md）

每个文件记录一道题的证据推理过程：
- 关联的问题和推测手册
- 引用的手册文件和行号
- 证据原文摘录
- 图片选择决策
- 最终答案策略

## 手册覆盖范围

### 中文手册（21 份）

冰箱、吹风机、电钻、儿童电动摩托车、发电机、功能键盘、健身单车、健身追踪器、烤箱、可编程温控器、空调、空气净化器、蓝牙激光鼠标、摩托艇、人体工学椅、水泵、洗碗机、相机、蒸汽清洁机、VR 头显、手册内容总览

### 英文手册（21 份）

Bosch Microwave、Brother Safety Guide、Canon EOS 20D、Color E-Reader、Color Television、Hydrabuds ANC、Instant Pot Duo Crisp、Motherboard、MV Camera、Nespresso CitiZ D111、Outdoor Grill、Philips Airfryer、Philips Sonicare Prestige、Philips XL490 XL495、Roomba i5、Toro Z Master 4000、Twin-Tub Washing Machine、Yamaha 210FSH 2021、Yamaha Snowmobile、Yamaha WaveRunner 2005、手册内容总览

## 与 InterX 其他包的关系

该数据集的问答流程对应 InterX 系统的完整 pipeline：

```
问题 (question.csv)
  │
  ▼  手册路由（手册内容总览.md）
  │
  ▼  检索（retrieval 包）
  │
  ▼  答案生成（answer 包）
  │── content: 答案正文（含 <PIC> 占位符）
  │── images: 图片 ID 列表
  │── evidence_refs: 证据来源（文件 + 行号）
  │
  ▼  知识图谱扩展（kg 包，可选）
```

`evidence_refs` 中的文件路径和行号可直接映射到 `process` 包的 chunk 产物，用于验证检索和回答的准确性。

## 使用方式

### 评估答案质量

```bash
# 查看某题的完整答案和证据
cat InterX/agentic-rag/answers/ch-answers/per_question/100.json | python3 -m json.tool

# 查看证据笔记
cat InterX/agentic-rag/answers/ch-answers/evidence-notes/100.md

# 统计答题完成率
python3 -c "
import csv
with open('InterX/agentic-rag/ch-todo.csv', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
done = sum(1 for r in rows if r['status'] == 'done')
print(f'中文: {done}/{len(rows)} 已完成')
"
```

### 使用 .agents 技能批量生成答案

agentic-rag 包内含两个 AI Agent 技能，用于批量生成答案：

#### answer-ch-agentic-rag（中文批量答题）

```bash
# 技能位置
InterX/agentic-rag/.agents/skills/answer-ch-agentic-rag/SKILL.md
```

该技能指导 AI Agent 逐题处理中文问题集：
1. 根据 `ch-todo.csv` 中的 `status` 列筛选待答题
2. 按 `manual_guess` 列路由到对应手册
3. 在手册中检索证据，生成带 `<PIC>` 占位符和 `evidence_refs` 的结构化答案
4. 将答案写入 `per_question/{id}.json`，更新 `ch-todo.csv` 状态

#### answer-agentic-rag（英文批量答题）

```bash
# 技能位置
InterX/agentic-rag/.agents/skills/answer-agentic-rag/SKILL.md
```

流程与中文技能相同，但处理英文问题集（`en-todo.csv` → `en-manual/` → `en-answers/`）。

#### 辅助脚本

```bash
# 同步答案到 JSONL 汇总文件
InterX/agentic-rag/.agents/scripts/sync_answers.py

# 同步中文答案
InterX/agentic-rag/.agents/scripts/sync_zh_answers.py

# 批量运行中文答题（顺序模式，用于调试）
InterX/agentic-rag/.agents/scripts/run_zh_sequential.py

# 批量运行中文答题（批量模式，用于生产）
InterX/agentic-rag/.agents/scripts/run_zh_batch.py

# 生成中文手册总览
InterX/agentic-rag/.agents/scripts/gen_zh_manual_overview.py
```

## 相关包

- `answer`：答案生成管道，本数据集的答案由该包生成
- `retrieval`：检索引擎，本数据集的证据来源由该包检索
- `process`：数据预处理层，本数据集的手册 chunk 由该包生成
- `kg`：知识图谱层，`evidence_refs` 中的跨章节证据可由该包扩展
