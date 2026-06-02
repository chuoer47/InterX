# KG 包已有测试

路径：`InterX/kg/tests/`

## 图存储（test_store.py）

| 测试函数 | 验证内容 |
|---------|---------|
| `test_init_creates_root` | 初始化创建数据库根目录 |
| `test_upsert_and_count` | 节点插入和计数 |
| `test_semantic_point_and_relation` | SemanticPoint 和 SemanticRelation 的创建和查询 |
| `test_traverse_bfs` | BFS 遍历（多跳扩展） |
| `test_link_chunk_to_sp` | SmallChunk → SemanticPoint 的 MENTIONS 边 |
| `test_sp_to_chunks` | SemanticPoint → SmallChunk 的 GROUNDED_IN 边 |
| `test_drop_manual` | 删除单个手册的图数据 |

## 图构建器（test_builder.py）

| 测试函数 | 验证内容 |
|---------|---------|
| `test_load_valid_jsonl` | 加载有效的 JSONL chunk 文件 |
| `test_load_missing_file` | 缺失文件的异常处理 |
| `test_build_manual_writes_graph` | 单手册图构建（mock LLM） |
| `test_build_manual_with_mock_relations` | 带 mock 语义关系的图构建 |

## 图扩展器（test_expander.py）

| 测试函数 | 验证内容 |
|---------|---------|
| `test_defaults` | ExpansionResult 默认值 |
| `test_expand_empty_seeds` | 空种子 → 空结果 |
| `test_expand_missing_db` | 缺失数据库 → 空结果 |
| `test_expand_returns_results` | 集成测试：扩展返回结果 |
| `test_expand_respects_max_limit` | max_expanded 上限生效 |
| `test_expand_deduplicates` | 扩展结果去重 |

## 图检索器（test_retriever.py）

| 测试函数 | 验证内容 |
|---------|---------|
| `test_empty_seed_returns_empty` | 空种子 → 空结果 |
| `test_expand_2hop_chain` | 2 跳链式扩展 |
| `test_seed_chunks_excluded_from_expansion` | 种子 chunk 不在扩展结果中 |
| `test_stats` | 统计信息正确 |
| `test_no_manual_id_returns_empty` | 无 manual_id → 空结果 |

## 图结构完整性（test_graph_retrieval.py）

| 测试函数 | 验证内容 |
|---------|---------|
| `test_all_manuals_have_small_chunks` | 所有手册都有 small chunk |
| `test_all_manuals_have_manual_node` | 所有手册都有 Manual 节点 |
| `test_hierarchy_edges_exist` | 层级边（HAS_BIG/MID/SMALL）存在 |
| `test_co_evidence_edges_exist` | CO_EVIDENCE 边存在 |
| `test_semantic_edges_exist` | SEMANTIC 边存在 |
| `test_question_nodes_exist` | Question 节点存在 |
| `test_answers_edges_exist` | ANSWERS 边存在 |
| `test_co_evidence_neighbors_exist` | CO_EVIDENCE 邻居可达 |
| `test_co_evidence_different_sections` | CO_EVIDENCE 连接不同章节 |
| `test_2hop_via_question` | 通过 Question 节点的 2 跳遍历 |
| `test_semantic_neighbors_exist` | SEMANTIC 邻居可达 |
| `test_semantic_has_description` | SEMANTIC 边有描述信息 |
