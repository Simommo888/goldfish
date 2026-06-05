# Goldfish 使用与维护说明

本文件是 `scripts/goldfish` 模块的详细说明。根目录 `README.md` 适合快速了解项目，本文件更适合日常运行、维护和二次开发。

## 1. Goldfish 是什么

Goldfish 是一个运行在 CLI 中的 AI 情报与知识沉淀 Agent。

它的核心能力包括：

- 每日 AI 情报采集
- AI 关键人物公开专业动态追踪
- 论文、开源项目、产品动态追踪
- 本地 RAG 知识库查询
- 公共网络检索
- RAG 优先、联网补充的组合查询
- 对话式工具调用
- plan and execute Agent Loop
- Obsidian / Markdown 知识沉淀
- 飞书通知预留与测试

## 2. 运行方式

进入项目根目录：

```powershell
cd D:\goldfish
```

安装依赖：

```powershell
python -m pip install -r scripts\goldfish\requirements.txt
```

安装为全局命令：

```powershell
python -m pip install -e .
```

启动：

```powershell
goldfish
```

未安装全局命令时：

```powershell
python scripts\goldfish\cli.py
```

## 3. 常用命令

### 对话

```powershell
goldfish
goldfish chat
goldfish chat --once "帮我查一下春天相关内容"
```

### RAG 和知识库

```powershell
goldfish lookup "春天相关内容"
goldfish rag ask "春天相关内容"
goldfish rag search "春天"
goldfish rag status
```

### 联网检索

```powershell
goldfish web "今天发生的 AI 大事" --search-provider news
goldfish web "MCP server business opportunities" --search-provider tavily
```

### Agent Loop

```powershell
goldfish agent "research MCP server commercial opportunities" --max-steps 3
goldfish agent "search previous RAG notes" --no-llm --max-steps 3
```

### 每日情报

```powershell
goldfish run
goldfish dry-run --verbose
goldfish weekly
```

### 诊断与工具

```powershell
goldfish doctor
goldfish tools
goldfish skills
goldfish config check
```

### Memory

```powershell
goldfish memory show
goldfish memory remember "我更关注 AI Agent 商业化" --kind preference
goldfish memory forget "AI Agent 商业化"
goldfish memory review
```

### 飞书通知

```powershell
goldfish notify status
goldfish notify test
goldfish notify qr
```

## 4. 配置模型

推荐通过 setup 配置：

```powershell
goldfish setup
```

进入后输入：

```text
/model
```

然后选择模型供应商，并输入 API Key。

支持方向：

- DeepSeek
- OpenAI
- OpenAI-compatible provider

API Key 必须通过环境变量读取，不应写入项目文件。

当前默认设置位于：

```text
scripts/goldfish/config/settings.json
```

示例：

```json
{
  "use_llm": true,
  "llm_provider": "deepseek",
  "llm_model": "deepseek-v4-pro",
  "llm_base_url": "https://api.deepseek.com"
}
```

## 5. 配置本机代理

如果需要通过本机代理联网：

```powershell
$env:HTTP_PROXY="http://127.0.0.1:7897"
$env:HTTPS_PROXY="http://127.0.0.1:7897"
```

## 6. RAG 配置

RAG 配置文件：

```text
scripts/goldfish/config/rag.json
```

默认配置：

```json
{
  "enabled": true,
  "mode": "http",
  "base_url": "http://127.0.0.1:8020",
  "health_endpoint": "/api/health",
  "stats_endpoint": "/api/rag/stats",
  "ask_endpoint": "/api/rag/ask",
  "search_endpoint": "/api/rag/search",
  "retrieval_mode": "hybrid",
  "top_k": 8,
  "use_llm": false,
  "timeout_seconds": 20
}
```

可用环境变量覆盖：

```powershell
$env:GOLDFISH_RAG_BASE_URL="http://127.0.0.1:8020"
```

当前 RAG 工具：

- `rag_status`：检查知识库服务状态
- `rag_search`：检索相关片段
- `rag_query`：向知识库提问
- `knowledge_lookup`：先查 RAG，再查联网搜索

## 7. 联网搜索配置

搜索配置文件：

```text
scripts/goldfish/config/search_providers.json
```

当前搜索链路：

```text
Tavily -> Jina -> Hacker News Algolia -> GDELT -> DuckDuckGo
```

常用环境变量：

```powershell
$env:TAVILY_API_KEY="你的 Tavily API Key"
$env:JINA_API_KEY="你的 Jina API Key"
```

说明：

- Tavily 适合 Agentic Web Research
- Jina 适合 LLM 可读的网页搜索结果
- Hacker News Algolia 适合技术社区信号
- GDELT 适合公共新闻检索
- DuckDuckGo 是无 Key fallback

## 8. ToolRegistry

核心文件：

```text
scripts/goldfish/modules/tool_registry.py
```

当前主要工具：

```text
run_daily
dry_run
weekly
config_check
doctor
memory_show
memory_remember
memory_forget
memory_review
history
search
rag_query
rag_search
rag_status
knowledge_lookup
web_search
skills
external_cli
source_health
notify_status
notify_test
agent
tools
```

设计原则：

- 所有工具统一注册
- 工具有 mutating 标记
- 工具有 timeout 标记
- Agent Loop 只能调用允许列表中的工具
- 不允许绕过 ToolRegistry 直接执行危险动作

## 9. Agent Loop

核心文件：

```text
scripts/goldfish/modules/agent_loop.py
```

工作流：

```text
parse goal
make plan
select tool
execute tool
observe
revise or stop
final answer
```

任务工作区：

```text
scripts/goldfish/output_cache/tasks/task-YYYYMMDD-HHMMSS-xxxx/
```

每次任务会记录：

```text
goal.md
plan.md
selected_skills.json
skills.md
memory_context.md
failure_policy.json
observations.json
tool_calls.jsonl
plan_revisions.jsonl
execution_state.json
final.md
```

安全边界：

- 不执行任意 shell
- 只走 ToolRegistry
- 不保存 API Key
- 工具结果过长会截断
- 写入失败不能导致整个 Agent 崩溃
- 默认 bounded steps，不无限循环

## 10. Skills

Skills 目录：

```text
scripts/goldfish/skills/
```

Skills 是轻量任务说明，不是工具实现本身。它们用于告诉 Agent 某类任务应该如何处理。

当前包括：

```text
business-idea
internet-search
jina-search
knowledge-routing
query-expansion
retrieval-planning
retrieval-review
source-curation
source-evaluation
tavily-search
trend-analysis
web-research
weekly-review
```

## 11. CLI 输出规范

Goldfish 是 CLI Agent，不是网页聊天机器人。

检索类输出应保持：

- 简洁
- 可扫描
- 可复制
- 不刷屏
- 不暴露内部技术细节
- 有来源和引用

推荐结构：

```text
goldfish > analyzing query...
goldfish > searching knowledge base...
goldfish > found 12 relevant chunks
goldfish > searching web...
goldfish > selected 3 sources

sources:
  [1] 标题 - 路径

answer:
根据知识库内容给出答案。[1]

references:
  [1] 标题 - 路径
```

禁止直接暴露：

```text
embedding_score
rerank_score
top_k
internal prompt
API Key
```

## 12. 每日 AI 情报工作流

运行：

```powershell
goldfish run
```

Dry-run：

```powershell
goldfish dry-run --verbose
```

主流程：

1. 读取配置
2. 抓取公开来源
3. 抓取人物公开专业动态
4. 抓取论文、开源项目、产品动态
5. 合并结果
6. 去重
7. 分类
8. 评分
9. LLM 或规则摘要
10. 生成 Markdown
11. 保存 Raw JSON
12. 更新 Dashboard
13. 必要时生成周报和沉淀草稿

输出目录：

```text
04_Resources/AI-News/Daily
04_Resources/AI-News/Weekly
04_Resources/AI-News/People-Watch
04_Resources/AI-News/Raw
04_Resources/AI-News/Reports
```

## 13. 知识沉淀

Goldfish 会把高价值信息引导到：

```text
05_Permanent-Notes/AI-Trends
11_Business-Ideas/AI-News-Inspirations
09_Prompts/AI-News
02_Projects/AI-News-Ideas
```

相关配置：

```json
{
  "generate_knowledge_report": true,
  "auto_create_knowledge_drafts": true,
  "draft_write_mode": "auto",
  "knowledge_report_limit": 8,
  "knowledge_min_score": 5
}
```

## 14. 配置文件

```text
config/settings.json           主设置
config/rag.json                RAG 服务配置
config/search_providers.json   联网搜索配置
config/tool_intents.json       自然语言意图配置
config/sources.json            AI 信息源
config/people.json             AI 人物源
config/keywords.json           关键词和评分方向
config/llm_prompts.json        LLM prompt
config/agent_profile.json      Agent 角色设定
config/external_tools.json     外部 CLI 工具白名单
```

## 15. 关键 Python 模块

```text
modules/tool_registry.py       工具注册中心
modules/conversation_agent.py  对话主循环
modules/command_router.py      命令和自然语言路由
modules/tool_planner.py        工具规划
modules/intent_router.py       配置化意图匹配
modules/agent_loop.py          Agent Loop
modules/rag_client.py          RAG 客户端
modules/web_researcher.py      联网检索
modules/response_formatter.py  输出格式
modules/agent_memory.py        Memory
modules/setup_agent.py         setup 向导
modules/notifier.py            通知
modules/feishu_qr_setup.py     飞书二维码配置
```

## 16. 测试

编译检查：

```powershell
python -m compileall -q scripts\goldfish
```

单元测试：

```powershell
python -m unittest scripts.goldfish.tests.test_basic
```

测试文件：

```text
scripts/goldfish/tests/test_basic.py
```

## 17. GitHub Actions

工作流目录：

```text
.github/workflows/
```

如启用自动日报，需要在 GitHub Secrets 中配置对应模型 API Key。

不要把 API Key 写入仓库。

## 18. 安全边界

Goldfish 必须遵守：

1. 只处理公开信息
2. 不抓取私人信息
3. 不追踪八卦
4. 不绕过登录
5. 不绕过反爬
6. 不保存 Cookie
7. 不提交 API Key
8. 不生成虚假来源
9. 不编造人物观点
10. 无法抓取时标记失败或待人工查看

## 19. 当前限制

- Agent Loop 仍是第一版有限步计划执行
- 最终回答的事实核验仍依赖来源质量
- RAG 需要外部知识库服务已启动
- 联网搜索质量依赖第三方服务和网络状态
- 启动页视觉在不同终端字体下可能有差异
- 复杂任务还需要更强的工具选择和多步反思能力

## 20. 后续优化方向

1. 把工具调用过程升级为真正的事件流
2. 增强引用式 LLM 综合回答
3. 给 RAG 增加 rerank、来源可信度和冲突检测
4. 减少自然语言意图硬编码，更多依赖 tool schema 和 skill 描述
5. 增加端到端测试：RAG、联网搜索、飞书、日报生成
6. 完善 Memory 的自动提取、确认、冲突和过期策略
7. 优化 CLI 视觉规范，统一 Goldfish 风格

