# Goldfish

Goldfish 是一个运行在 CLI 中的 AI 情报与知识沉淀 Agent。

它面向 Obsidian / Markdown 个人知识库，核心目标是把公开信息检索、本地 RAG 查询、AI 情报日报、知识沉淀草稿、对话式工具调用整合到一个可维护的命令行智能体中。

## 项目定位

Goldfish 不是单纯的新闻脚本，也不是普通聊天机器人。它更像一个面向个人知识库的检索类 Agent：

- 先查本地 RAG 知识库，再用联网搜索补充
- 通过自然语言调用工具
- 自动生成 AI 情报日报和趋势周报
- 把高价值信息沉淀成永久笔记、商业想法、Prompt、项目灵感
- 以 CLI 友好的方式输出检索过程、来源和答案

## 当前能力

### CLI 对话

直接运行：

```powershell
goldfish
```

或：

```powershell
goldfish chat
```

Goldfish 支持自然语言触发工具，也支持英文 slash command，例如：

```text
/model
/agent
/tools
/memory
/notify
/help
```

### RAG 优先查询

Goldfish 已接入本地 RAG 工具：

- `rag_query`
- `rag_search`
- `rag_status`
- `knowledge_lookup`

默认策略：

```text
先查本地 RAG
再查公共网络
两块结果分开输出
联网结果只作补充，不覆盖本地知识库
```

示例：

```powershell
goldfish lookup "春天相关内容"
goldfish rag ask "春天相关内容"
goldfish rag search "春天"
goldfish rag status
```

### 联网搜索

Goldfish 当前搜索链路：

```text
Tavily -> Jina -> Hacker News Algolia -> GDELT -> DuckDuckGo
```

搜索配置文件：

```text
scripts/goldfish/config/search_providers.json
```

示例：

```powershell
goldfish web "今天发生的 AI 大事" --search-provider news
```

如果使用本机代理：

```powershell
$env:HTTP_PROXY="http://127.0.0.1:7897"
$env:HTTPS_PROXY="http://127.0.0.1:7897"
```

### Agent Loop

Goldfish 支持第一版 plan and execute Agent Loop：

```powershell
goldfish agent "research MCP server commercial opportunities" --max-steps 3
```

Agent Loop 会：

1. 解析自然语言目标
2. 生成计划
3. 从 ToolRegistry 中选择工具
4. 执行工具
5. 记录 observation
6. 必要时修正计划
7. 输出最终总结

安全边界：

- 不执行任意 shell
- 不绕过 ToolRegistry
- 每步有超时
- 总任务有超时
- 失败过多会停止
- 不保存 API Key

任务记录目录：

```text
scripts/goldfish/output_cache/tasks/
```

### AI 情报日报

Goldfish 可以抓取公开 AI 信息源，并生成 Markdown 日报：

```powershell
goldfish run
```

Dry-run，不写入 Obsidian：

```powershell
goldfish dry-run --verbose
```

生成周报：

```powershell
goldfish weekly
```

输出位置：

```text
04_Resources/AI-News/Daily
04_Resources/AI-News/Weekly
04_Resources/AI-News/People-Watch
04_Resources/AI-News/Raw
04_Resources/AI-News/Reports
```

### 知识沉淀

Goldfish 可以把高价值信息沉淀为：

- 永久笔记
- 商业想法
- Prompt
- 项目灵感

相关输出目录：

```text
05_Permanent-Notes/AI-Trends
11_Business-Ideas/AI-News-Inspirations
09_Prompts/AI-News
02_Projects/AI-News-Ideas
```

草稿写入模式由 `settings.json` 控制：

```json
{
  "draft_write_mode": "auto"
}
```

可选值：

```text
off
suggest
ask
auto
```

### Memory

Goldfish 支持长期记忆：

```powershell
goldfish memory show
goldfish memory remember "我更关注 AI Agent 商业化" --kind preference
goldfish memory forget "AI Agent 商业化"
goldfish memory review
```

Memory 文件：

```text
scripts/goldfish/output_cache/agent_memory.json
```

### 飞书通知

查看通知状态：

```powershell
goldfish notify status
```

发送测试消息：

```powershell
goldfish notify test
```

临时二维码配置：

```powershell
goldfish notify qr
```

飞书 webhook 和 secret 只写入用户级环境变量，不写入项目文件。

## 安装

进入项目目录：

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

安装后：

```powershell
goldfish
```

如果还没有安装为全局命令，也可以直接运行：

```powershell
python scripts\goldfish\cli.py
```

## 配置模型

进入 setup：

```powershell
goldfish setup
```

在 setup 中输入：

```text
/model
```

然后选择 DeepSeek / OpenAI / OpenAI-compatible，并输入对应 API Key。

当前默认模型配置在：

```text
scripts/goldfish/config/settings.json
```

示例：

```json
{
  "llm_provider": "deepseek",
  "llm_model": "deepseek-v4-pro",
  "llm_base_url": "https://api.deepseek.com"
}
```

注意：不要把 API Key 写入配置文件或提交到仓库。

## 配置 RAG

RAG 配置文件：

```text
scripts/goldfish/config/rag.json
```

默认连接：

```json
{
  "enabled": true,
  "mode": "http",
  "base_url": "http://127.0.0.1:8020",
  "retrieval_mode": "hybrid",
  "top_k": 8
}
```

可以用环境变量覆盖：

```powershell
$env:GOLDFISH_RAG_BASE_URL="http://127.0.0.1:8020"
```

## 目录结构

```text
D:\goldfish
  README.md
  pyproject.toml
  Dockerfile
  docker-compose.yml
  scripts/goldfish/
    cli.py
    goldfish.py
    config/
    modules/
    skills/
    templates/
    tests/
    tui/
  04_Resources/AI-News/
  05_Permanent-Notes/
  09_Prompts/
  11_Business-Ideas/
```

## 核心模块

```text
scripts/goldfish/cli.py                     CLI 主入口
scripts/goldfish/modules/tool_registry.py   工具注册中心
scripts/goldfish/modules/conversation_agent.py
scripts/goldfish/modules/command_router.py
scripts/goldfish/modules/tool_planner.py
scripts/goldfish/modules/agent_loop.py
scripts/goldfish/modules/rag_client.py
scripts/goldfish/modules/web_researcher.py
scripts/goldfish/modules/response_formatter.py
scripts/goldfish/modules/agent_memory.py
scripts/goldfish/modules/setup_agent.py
```

## CLI 输出约束

Goldfish 是 CLI Agent，不是网页聊天机器人。

检索类输出默认遵循：

```text
goldfish > analyzing query...
goldfish > searching knowledge base...
goldfish > found 12 relevant chunks
goldfish > searching web...
goldfish > selected 3 sources

sources:
  [1] 标题 - 路径

answer:
基于来源给出答案。[1]

references:
  [1] 标题 - 路径
```

原则：

- 短句
- 可扫描
- 可复制
- 不刷屏
- 不暴露 embedding_score / rerank_score / top_k 等内部细节
- 有来源和引用

## 测试

编译检查：

```powershell
python -m compileall -q scripts\goldfish
```

单元测试：

```powershell
python -m unittest scripts.goldfish.tests.test_basic
```

## 安全边界

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
10. 无法抓取时明确降级

## 当前限制

- Agent Loop 是第一版有限步执行，还不是完整通用自主 Agent
- 联网搜索质量依赖 Tavily / Jina 等外部服务
- 本地 RAG 需要独立服务运行
- 启动页视觉仍受终端尺寸、字体、编码影响
- 对复杂问题的最终综合回答仍需要继续增强引用式生成能力

