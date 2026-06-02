# Answer 包已有测试

路径：`InterX/answer/tests/`

## 数据模型（test_foundation.py）

| 测试函数 | 验证内容 |
|---------|---------|
| `test_answer_payload` | AnswerPayload 序列化（content + images） |
| `test_answer_payload_no_images` | 无图片时 images 默认为空列表 |
| `test_granularity_answer` | GranularityAnswer 序列化 |
| `test_recall_meta` | RecallMeta 序列化 |
| `test_qa_result` | QAResult 完整序列化 |
| `test_batch_record` | BatchRecord 序列化 |

## 上下文组装（test_images_context.py）

| 测试函数 | 验证内容 |
|---------|---------|
| `test_format_context_empty` | 空 chunk 列表 → 空 JSON |
| `test_format_context_basic` | 基本格式化（rank, doc_name, section_title, content） |
| `test_format_context_truncation` | **预算截断**：超出 max_chars 时二分搜索截断最后一条证据 |
| `test_format_context_multiple` | 多条证据的格式化 |

## 图片一致性（test_images_context.py）

| 测试函数 | 验证内容 |
|---------|---------|
| `test_repair_inline_markers` | LLM 输出的各种图片标记（`[图片:xxx]`、`<PIC>` 等）统一修复为 `<PIC>` |
| `test_repair_inline_markers_unknown` | 未知格式的图片标记处理 |
| `test_normalize_answer_basic` | 归一化：`<PIC>` 与 images 列表按位置对齐 |
| `test_normalize_answer_no_images` | 无图片时的归一化 |
| `test_normalize_answer_dedup` | 去重：重复图片和无文字支撑的 `<PIC>` 被移除 |

## 路由（test_router.py）

| 测试函数 | 验证内容 |
|---------|---------|
| `test_images_always_route_to_manual` | 有图片时跳过路由，直接走 RAG |
| `test_no_images_no_images_param` | 无图片时 LLM 路由判断（mock） |
| `test_route_general` | 通用客服问题路由到 general |
| `test_route_defaults_to_manual_on_error` | API 故障时默认走 RAG |
| `test_route_defaults_to_manual_on_bad_json` | LLM 返回无效 JSON 时默认走 RAG |
| `test_answer_general_returns_payload` | 通用回答返回 AnswerPayload |
| `test_answer_general_images_always_empty` | 通用回答无产品图片 |
| `test_router_prompt_has_xml_tags` | router.md 含 XML 标签 |
| `test_router_prompt_formats_correctly` | 模板变量正确替换 |
| `test_general_answer_prompt_has_xml_tags` | general_answer.md 含 XML 标签 |
