"""Generate weekly AI trend reports from recent daily reports."""

from __future__ import annotations

import re
from typing import Dict, List

from .utils import week_string


def _extract_headings(markdown: str, limit: int = 10) -> List[str]:
    headings = []
    for line in markdown.splitlines():
        if line.startswith("### "):
            headings.append(re.sub(r"^###\\s+", "", line).strip())
        if len(headings) >= limit:
            break
    return headings


def generate_weekly_report(date_text: str, recent_daily_reports: List[Dict[str, str]]) -> str:
    week = week_string(date_text)
    headings: List[str] = []
    for report in recent_daily_reports:
        headings.extend(_extract_headings(report.get("content", ""), limit=5))
    headings = headings[:10]
    important = "\n".join(f"{idx}. {title}" for idx, title in enumerate(headings, start=1)) or "暂无足够日报内容。"
    source_links = "\n".join(
        f"- [[04_Resources/AI-News/Daily/AI情报日报-{report['date']}]]"
        for report in recent_daily_reports
    ) or "- 暂无日报链接。"

    return f"""# AI 趋势周报 - {week}

## 本周最重要的 10 条 AI 动态

{important}

## 本周 AI 大佬观点

- 从本周 People-Watch 与日报中筛选可复用观点，避免沉淀八卦和无来源观点。

## 本周 Agent / RAG / AI Coding 趋势

- 重点观察 Agent、RAG、AI Coding、MCP、知识库和工作流自动化是否出现新工具、新框架或新商业场景。

## 本周热门开源项目

- 优先查看 GitHub Trending、Hugging Face Spaces 和项目 README，判断是否能复用于自己的 AI 应用开发。

## 本周值得研究的论文

- 优先选择能转化成工程方法、评测方法、RAG/Agent 架构或产品能力的论文。

## 本周商业化机会

- 观察企业私有部署、客户支持、教育、开发者工具、流程自动化和知识库产品机会。

## 下周建议关注方向

- Agent 工具调用可靠性
- RAG 数据质量和评测
- AI Coding 工作流
- MCP 生态
- 技术变现案例

## 建议沉淀的永久笔记

- [ ] 本周最重要的 AI 开发观点
- [ ] 一个 Agent / RAG 工程方法
- [ ] 一个 AI Coding 工作流经验

## 建议新增的商业想法

- [ ] 一个可落地的 AI 应用产品机会
- [ ] 一个可收费的工作流自动化场景

## 本周参考日报

{source_links}
"""
