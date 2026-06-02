# Prompt 结构验证报告

## 实验数据概览

对 InterX 系统中全部 Prompt 模板文件和代码中的内联 Prompt 进行 XML 结构完整性检查。检查范围涵盖 answer 包（8 个模板）、chat 包（2 个模板）、pipeline.py 中的 user message XML 标签、以及 kg/llm_client.py 中的内联 Prompt。

## 指标

| 指标 | 说明 |
|------|------|
| XML 标签完整性 | 每个模板是否包含所有必需的语义标签（`<role>`、`<output_format>` 等） |
| 标签闭合率 | 每个开标签 `<tag>` 是否有对应的闭标签 `</tag>` |
| 模板变量完整性 | 使用 `str.format()` 的模板中的 `{variable}` 是否完整 |
| 代码一致性 | pipeline.py 中 user message 的 XML 标签是否与模板匹配 |

## 实验开展

1. 定义每个 Prompt 文件的必需标签清单（来自 `data/checklist.json`）
2. 读取每个文件，检查必需标签是否存在
3. 检查标签闭合（每个 `<tag>` 是否有 `</tag>`）
4. 检查模板变量（`{question}`、`{history}` 等）是否在文件中出现
5. 检查 `pipeline.py` 和 `kg/llm_client.py` 中的 user message XML 标签

## 结果

| 检查项 | 结果 |
|--------|------|
| answer/router.md | ✅ 5/5 标签就位 |
| answer/general_answer.md | ✅ 4/4 标签就位 |
| answer/small_answer.md | ✅ 5/5 标签就位 |
| answer/mid_answer.md | ✅ 5/5 标签就位 |
| answer/big_answer.md | ✅ 5/5 标签就位 |
| answer/ensemble.md | ✅ 4/4 标签就位 |
| answer/query_rewrite.md | ✅ 4/4 标签就位 + 2 模板变量 |
| answer/judge.md | ✅ 3/3 标签就位 |
| chat/rewrite.md | ✅ 5/5 标签就位 + 2 模板变量 |
| chat/summarize.md | ✅ 3/3 标签就位 + 1 模板变量 |
| pipeline.py user message | ✅ 7/7 XML 标签就位 |
| kg/llm_client.py 内联 prompt | ✅ 5/5 XML 标签就位 |

**总计：12/12 通过（100%）**

## 分析

所有 Prompt 模板的 XML 结构化改造完整且一致。标签命名在 answer、chat、kg 三个包之间保持统一（共用 `<role>`、`<output_format>` 等标签名），降低了维护成本。使用 `str.format()` 的模板（query_rewrite、chat rewrite/summarize）中的变量均已正确设置，无遗漏。pipeline.py 中的 user message XML 标签与模板中的标签完全匹配，确保 LLM 能正确解析结构化输入。

该验证项无风险，可放心部署。
