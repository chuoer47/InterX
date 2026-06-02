# InterX 验证报告

## 验证结果总览

| 验证项 | 核心指标 | 结果 | 状态 |
|--------|---------|------|------|
| Prompt 结构 | XML 标签完整性 | 12/12（100%） | ✅ 通过 |
| 路由准确率 | 通用/产品分类 | 90.0%（27/30） | ✅ 通过 |
| KG 扩展效果 | 跨章节 chunk 扩展 | 100%（5/5，+8 chunks） | ✅ 通过 |
| 回答质量 | 三类问题端到端 | 100%（3/3） | ✅ 通过 |
| 检索质量 | Recall@5 / @10 / @20 | 95.9% / 96.5% / 97.7% | ✅ 通过 |
| 长对话模拟 | 5 轮多轮对话 | 5/5 全检查通过 | ✅ 通过 |
| 语义缓存 | 精确匹配 + 语义匹配 | 精确 100%，语义 67% | ✅ 通过 |
| 五重分词效果 | BM25 召回率对比 | 纯jieba 9.9% → 五重 95.9%（+86%） | ✅ 通过 |
| 降级容错 | Dense/Rerank 故障降级 | 12/12 全部正确降级 | ✅ 通过 |

## 已有单元测试覆盖

各包 `tests/` 目录下的已有测试按验证维度分类，详见：

| 包 | 测试文件 | 覆盖维度 | 说明 |
|---|---------|---------|------|
| answer | [answer-tests.md](answer-tests.md) | 数据模型、上下文截断、图片一致性、路由 | 21 个测试函数 |
| retrieval | [retrieval-tests.md](retrieval-tests.md) | 分词、RRF 融合、层次聚合、上下文组装 | 13 个测试函数 |
| kg | [kg-tests.md](kg-tests.md) | 图存储、图构建、图扩展、图检索、图结构完整性 | 30 个测试函数 |
| chat | [chat-tests.md](chat-tests.md) | API 端点、会话管理、记忆策略 | 21 个测试函数 |

**已有测试与集成验证的关系：**

| 维度 | 已有单元测试 | 集成验证 |
|------|------------|---------|
| 上下文截断 | ✅ `test_format_context_truncation` | — |
| `<PIC>` 一致性 | ✅ `test_repair_markers` + `test_normalize_dedup` | — |
| RRF 融合 | ✅ `test_rrf_fuse_*`（3 个） | ✅ retrieval-quality |
| 层次聚合 | ✅ `test_mid/big_hit_aggregation` | ✅ retrieval-quality |
| 分词 | ✅ `test_tokenize_*`（3 个） | ❌ 未做效果对比 |
| 路由 | ✅ `test_route_*`（mock） | ✅ routing（真实 LLM） |
| KG 扩展 | ✅ `test_expand_*`（mock） | ✅ kg-effect（真实图谱） |
| 记忆策略 | ✅ `test_sliding_*` | ✅ long-dialogue |
| 降级容错 | ❌ 无 | ❌ 未做 |

## 集成验证目录

```
verify/
├── README.md
├── answer-tests.md              # answer 包已有测试说明
├── retrieval-tests.md           # retrieval 包已有测试说明
├── kg-tests.md                  # kg 包已有测试说明
├── chat-tests.md                # chat 包已有测试说明
├── prompt-structure/            # Prompt XML 结构验证
│   ├── data/checklist.json
│   ├── run.py
│   └── results/
├── routing/                     # 路由准确率验证
│   ├── data/test_cases.json
│   ├── run.py
│   └── results/
├── kg-effect/                   # KG 扩展效果验证
│   ├── data/queries.json
│   ├── run.py
│   └── results/
├── answer-sanity/               # 回答质量抽样验证
│   ├── data/samples.json
│   ├── run.py
│   └── results/
├── retrieval-quality/           # 检索质量验证
│   ├── data/ground_truth.json
│   ├── data/manual_lookup.json
│   ├── data/line_indexes.json
│   ├── run.py
│   └── results/
├── long-dialogue/               # 长对话模拟验证
│   ├── data/conversation.json
│   ├── run.py
│   └── results/
└── semantic-cache/              # 语义缓存验证
    ├── run.py
    └── results/
```

## 运行方式

### 已有单元测试

```bash
cd InterX
python -m pytest answer/tests/ -v          # 21 个测试
python -m pytest retrieval/tests/ -v       # 13 个测试
python -m pytest kg/tests/ -v              # 30 个测试（需 kuzu）
python -m pytest chat/tests/ -v            # 21 个测试
```

### 集成验证

```bash
cd InterX/verify
python prompt-structure/run.py        # ~2s，纯本地
python routing/run.py                 # ~3min，30 次路由 LLM 调用
python kg-effect/run.py               # ~10s，检索 + 图遍历
python answer-sanity/run.py           # ~5min，3 次完整管道
python retrieval-quality/run.py       # ~15min，350 次检索
python long-dialogue/run.py           # ~5min，5 轮完整对话
python semantic-cache/run.py          # ~2s，精确匹配逻辑验证
```

## 扩展方式

要增加测试用例，只需编辑对应 `data/*.json` 文件，无需修改脚本。
