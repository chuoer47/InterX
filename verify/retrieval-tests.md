# Retrieval 包已有测试

路径：`InterX/retrieval/tests/`

## 分词器（test_retrieval.py）

| 测试函数 | 验证内容 |
|---------|---------|
| `test_tokenize_english` | 英文分词（ASCII token 提取） |
| `test_tokenize_chinese` | 中文分词（jieba + unigram + bigram + trigram） |
| `test_tokenize_empty` | 空文本降级处理 |

## RRF 融合（test_retrieval.py）

| 测试函数 | 验证内容 |
|---------|---------|
| `test_rrf_fuse_single_channel` | 单通道融合（无竞争） |
| `test_rrf_fuse_two_channels` | 双通道融合（Dense + BM25，验证权重和排名） |
| `test_rrf_fuse_empty` | 空输入处理 |

## 层次聚合（test_retrieval.py）

| 测试函数 | 验证内容 |
|---------|---------|
| `test_mid_hit_aggregation` | 小块按 mid_chunk_id 聚合为中块（双关键字排序） |
| `test_big_hit_aggregation` | 中块按 big_chunk_id 聚合为大块 |

## 上下文组装（test_retrieval.py）

| 测试函数 | 验证内容 |
|---------|---------|
| `test_assemble_context_small` | 小块上下文格式化 |
| `test_assemble_context_truncation` | 预算截断（至少保留 1 个 block） |
| `test_assemble_context_mid` | 中块上下文格式化（含子块摘要） |

## 数据模型（test_retrieval.py）

| 测试函数 | 验证内容 |
|---------|---------|
| `test_search_hit_to_dict` | SearchHit 序列化 |
| `test_hierarchical_result_to_dict` | HierarchicalResult 递归序列化 |
