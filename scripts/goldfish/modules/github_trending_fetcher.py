"""Lightweight GitHub Trending fetcher.

The parser only reads the public trending page. It does not log in and does not
attempt to bypass rate limits or anti-scraping controls.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from .utils import fetch_url, make_manual_item, now, strip_html, truncate


AI_REPO_KEYWORDS = [
    "agent",
    "rag",
    "llm",
    "ai-coding",
    "codex",
    "mcp",
    "vector database",
    "knowledge base",
    "embedding",
    "ai",
]


def _parse_github_trending(html: str, source: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    article_pattern = re.compile(r"<article\\b.*?</article>", flags=re.I | re.S)
    href_pattern = re.compile(r'<h2[^>]*>\\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', flags=re.I | re.S)
    desc_pattern = re.compile(r'<p[^>]*class="[^"]*color-fg-muted[^"]*"[^>]*>(.*?)</p>', flags=re.I | re.S)
    for article in article_pattern.findall(html):
        href_match = href_pattern.search(article)
        if not href_match:
            continue
        path = href_match.group(1).strip()
        title = strip_html(href_match.group(2)).replace(" ", "")
        desc_match = desc_pattern.search(article)
        description = truncate(strip_html(desc_match.group(1)) if desc_match else "", 500)
        text = f"{title} {description}".lower()
        if not any(keyword.lower() in text for keyword in AI_REPO_KEYWORDS):
            continue
        items.append(
            {
                "title": title,
                "url": "https://github.com" + path,
                "source_name": source.get("name", "GitHub Trending"),
                "source_category": "open_source",
                "source_priority": source.get("priority", 5),
                "published": "",
                "summary": description or "GitHub Trending AI 相关项目。",
                "raw_content": description,
                "fetched_at": now().isoformat(),
                "content_type": "open_source",
            }
        )
        if len(items) >= limit:
            break
    return items


def fetch_github_trending(
    sources: List[Dict[str, Any]],
    limit: int = 5,
    timeout: int = 10,
    allow_network: bool = True,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    github_sources = [source for source in sources if "github" in source.get("name", "").lower()]
    if not github_sources:
        return results
    source = github_sources[0]
    if not allow_network:
        return [
            make_manual_item(
                "GitHub Trending：dry-run 未联网抓取",
                source.get("url", "https://github.com/trending"),
                source.get("name", "GitHub Trending"),
                "open_source",
                "dry-run 模式默认不联网；真实运行时会轻量解析公开页面。",
            )
        ]
    try:
        html = fetch_url(source.get("url", "https://github.com/trending/python?since=daily"), timeout)
        parsed = _parse_github_trending(html, source, limit)
        if parsed:
            return parsed
        return [
            make_manual_item(
                "GitHub Trending：未解析到 AI 相关项目，待人工查看",
                source.get("url", "https://github.com/trending"),
                source.get("name", "GitHub Trending"),
                "open_source",
                "公开页面可访问但未解析到匹配关键词的 AI 项目。",
            )
        ]
    except Exception as exc:
        item = make_manual_item(
            "GitHub Trending：抓取失败，待人工查看",
            source.get("url", "https://github.com/trending"),
            source.get("name", "GitHub Trending"),
            "open_source",
            f"公开页面抓取失败：{exc}",
        )
        item["fetch_error"] = str(exc)
        return [item]
