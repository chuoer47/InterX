# Chat 包已有测试

路径：`InterX/chat/tests/`

## API 端点（test_api.py）

| 测试函数 | 验证内容 |
|---------|---------|
| `test_health` | `/health` 端点正常响应 |
| `test_auth_required` | 未认证请求返回 401 |
| `test_question_required` | 缺少 question 字段返回错误 |
| `test_question_empty` | 空 question 返回错误 |
| `test_list_sessions_empty` | 空用户无会话列表 |
| `test_get_session_not_found` | 不存在的会话返回 404 |
| `test_chat_endpoint_mocked` | `/chat` 端点基本功能（mock LLM） |
| `test_chat_with_images_mocked` | 带图片的 `/chat` 请求 |
| `test_image_bad_format` | 错误格式的图片返回错误 |
| `test_images_max_count` | 超过图片数量限制返回错误 |

## 数据模型与会话管理（test_chat.py）

| 测试函数 | 验证内容 |
|---------|---------|
| `test_turn_create` | Turn 对象创建 |
| `test_session_create` | Session 对象创建 |
| `test_session_to_dict` | Session 序列化 |
| `test_chat_response` | ChatResponse 对象 |
| `test_save_and_load_session` | 会话持久化（JSON 文件读写） |
| `test_load_nonexistent_session` | 加载不存在的会话返回 None |
| `test_list_sessions` | 列出会话 |
| `test_sliding_window_context` | **滑动窗口记忆策略** |
| `test_sliding_summary_context` | **滑动摘要记忆策略** |
| `test_empty_session_context` | 空会话的上下文 |
| `test_format_turns_text` | 对话历史格式化 |
