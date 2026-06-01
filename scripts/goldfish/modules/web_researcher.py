"""Public web research for goldfish.

Safety boundary: this module only uses public search result pages and public
web pages. It does not log in, store cookies, bypass anti-scraping protections,
or crawl unbounded link graphs.
"""

from __future__ import annotations

import json
import os
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List
from urllib.request import Request, urlopen

from .providers.registry import get_provider, resolve_llm_connection
from .storage import save_markdown
from .utils import USER_AGENT, fetch_url, kb_root, now, safe_filename, strip_html, today_string, truncate


SEARCH_URLS = [
    "https://lite.duckduckgo.com/lite/?q={query}",
    "https://duckduckgo.com/html/?q={query}",
]
MAX_PAGE_CHARS = 6000


def research_public_web(
    query: str,
    limit: int = 6,
    fetch_limit: int = 4,
    timeout: int = 12,
    use_llm: bool = True,
    save: bool = True,
    search_provider: str | None = None,
    root: Path | None = None,
) -> Dict[str, Any]:
    root = root or kb_root()
    query = query.strip()
    if not query:
        return {"query": query, "error": "query is required", "results": [], "pages": []}

    search_results = search_public_web(query, limit=limit, timeout=timeout, provider=search_provider)
    pages = fetch_research_pages(search_results[:fetch_limit], timeout=timeout)
    synthesis = synthesize_research(query, search_results, pages, use_llm=use_llm)
    markdown = generate_research_markdown(query, search_results, pages, synthesis)

    path = ""
    if save:
        path = str(save_research_report(query, markdown, root=root))

    return {
        "query": query,
        "search_provider": search_results[0].get("source", "") if search_results else "",
        "results_count": len(search_results),
        "pages_count": len(pages),
        "report_path": path,
        "synthesis": synthesis,
        "results": search_results,
        "pages": [_page_without_content(page) for page in pages],
    }


def search_public_web(query: str, limit: int = 6, timeout: int = 12, provider: str | None = None) -> List[Dict[str, Any]]:
    errors = []
    for search_provider in _search_provider_order(provider):
        try:
            if search_provider == "brave":
                results = search_brave_web(query, limit=limit, timeout=timeout)
            else:
                results = search_duckduckgo_html(query, limit=limit, timeout=timeout)
            if results:
                return results
            errors.append(f"{search_provider}: no results")
        except Exception as exc:
            errors.append(f"{search_provider}: {exc}")
            continue
    manual_url = SEARCH_URLS[0].format(query=urllib.parse.quote_plus(query))
    return [
        {
            "title": "No parseable search results",
            "url": manual_url,
            "snippet": "; ".join(errors[-4:]) or "The public search provider returned no parseable result blocks.",
            "source": "manual-review",
            "error": "no_results",
        }
    ]


def search_brave_web(query: str, limit: int = 6, timeout: int = 12) -> List[Dict[str, Any]]:
    api_key = os.environ.get("BRAVE_SEARCH_API_KEY") or os.environ.get("BRAVE_API_KEY")
    endpoint = os.environ.get("BRAVE_SEARCH_ENDPOINT", "https://api.search.brave.com/res/v1/web/search").rstrip("/")
    if not api_key:
        raise RuntimeError("missing BRAVE_SEARCH_API_KEY")
    url = endpoint + "?" + urllib.parse.urlencode({"q": query, "count": max(1, min(limit, 20))})
    payload = _fetch_json(
        url,
        timeout=timeout,
        headers={"X-Subscription-Token": api_key, "Accept": "application/json"},
    )
    return _brave_results_from_payload(payload, limit=limit)


def search_duckduckgo_html(query: str, limit: int = 6, timeout: int = 12) -> List[Dict[str, Any]]:
    errors = []
    for template in SEARCH_URLS:
        url = template.format(query=urllib.parse.quote_plus(query))
        try:
            html = fetch_url(url, timeout=timeout)
        except Exception as exc:
            errors.append(f"{url}: {exc}")
            continue
        parser = DuckDuckGoHTMLParser()
        parser.feed(html)
        results = [item for item in parser.results if _is_search_result_url(item.get("url", ""))][:limit]
        if results:
            return results
        errors.append(f"{url}: no parseable result blocks")
    raise RuntimeError("; ".join(errors[-2:]) or "DuckDuckGo returned no parseable result blocks")


def fetch_research_pages(results: List[Dict[str, Any]], timeout: int = 12) -> List[Dict[str, Any]]:
    pages: List[Dict[str, Any]] = []
    for result in results:
        url = result.get("url", "")
        if not _is_fetchable_url(url):
            pages.append({**result, "content": "", "fetch_status": "skipped", "error": "unsupported_url"})
            continue
        try:
            raw = fetch_url(url, timeout=timeout)
            text = truncate(strip_html(raw), MAX_PAGE_CHARS)
            pages.append({**result, "content": text, "fetch_status": "success", "error": ""})
        except Exception as exc:
            pages.append({**result, "content": "", "fetch_status": "failed", "error": str(exc)})
    return pages


def synthesize_research(
    query: str,
    results: List[Dict[str, Any]],
    pages: List[Dict[str, Any]],
    use_llm: bool = True,
) -> Dict[str, Any]:
    fallback = rule_based_synthesis(query, results, pages)
    if not use_llm:
        return fallback
    settings = {"llm_provider": "deepseek", "llm_model": "deepseek-v4-pro", "llm_base_url": "https://api.deepseek.com"}
    connection = resolve_llm_connection(settings)
    if not connection.get("api_key"):
        return fallback
    payload = {
        "query": query,
        "results": results[:8],
        "pages": [
            {
                "title": page.get("title", ""),
                "url": page.get("url", ""),
                "snippet": page.get("snippet", ""),
                "content": truncate(page.get("content", ""), 1800),
                "fetch_status": page.get("fetch_status", ""),
                "error": page.get("error", ""),
            }
            for page in pages[:5]
        ],
    }
    try:
        parsed = get_provider(settings).generate_json(
            [
                {
                    "role": "system",
                    "content": (
                        "You are goldfish research synthesis. Return JSON only. "
                        "Use only provided public sources. Do not invent URLs, facts, quotes, or claims."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Summarize this web research in Chinese with keys: "
                        "answer, key_points, useful_for_me, risks, next_actions, suggested_notes.\n\n"
                        + json.dumps(payload, ensure_ascii=False)
                    ),
                },
            ],
            temperature=0.2,
        )
        return {
            "mode": "llm",
            "answer": str(parsed.get("answer", "") or fallback["answer"]),
            "key_points": _list_of_str(parsed.get("key_points")) or fallback["key_points"],
            "useful_for_me": str(parsed.get("useful_for_me", "") or fallback["useful_for_me"]),
            "risks": _list_of_str(parsed.get("risks")) or fallback["risks"],
            "next_actions": _list_of_str(parsed.get("next_actions")) or fallback["next_actions"],
            "suggested_notes": _list_of_str(parsed.get("suggested_notes")) or fallback["suggested_notes"],
        }
    except Exception as exc:
        fallback["mode"] = "rule"
        fallback["llm_error"] = str(exc)
        return fallback


def rule_based_synthesis(query: str, results: List[Dict[str, Any]], pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    successful = [page for page in pages if page.get("fetch_status") == "success"]
    key_points = []
    for item in (successful or results)[:5]:
        title = item.get("title", "Untitled")
        snippet = item.get("snippet") or truncate(item.get("content", ""), 180)
        key_points.append(f"{title}: {snippet}")
    return {
        "mode": "rule",
        "answer": f"已围绕“{query}”检索公开网页，并抓取 {len(successful)} 个可访问页面。",
        "key_points": key_points,
        "useful_for_me": "可作为临时研究材料，继续沉淀为永久笔记、Prompt、项目灵感或商业想法。",
        "risks": [
            "搜索结果可能包含过时或低质量内容，需要人工核验。",
            "无法访问、反爬或需要登录的页面已跳过，不会绕过限制。",
        ],
        "next_actions": [
            "打开高价值来源核验原文。",
            "把可复用观点改写成自己的长期笔记。",
            "把可落地机会拆成 MVP 和验证实验。",
        ],
        "suggested_notes": ["[[05_Permanent-Notes]]", "[[11_Business-Ideas]]", "[[09_Prompts]]"],
    }


def generate_research_markdown(
    query: str,
    results: List[Dict[str, Any]],
    pages: List[Dict[str, Any]],
    synthesis: Dict[str, Any],
) -> str:
    date_text = today_string()
    result_lines = "\n".join(
        f"{index}. [{item.get('title', 'Untitled')}]({item.get('url', '')})  \n   {item.get('snippet', '')}"
        for index, item in enumerate(results, start=1)
    ) or "暂无搜索结果。"
    page_blocks = "\n\n".join(_page_block(index, page) for index, page in enumerate(pages, start=1)) or "暂无可抓取页面。"
    key_points = "\n".join(f"- {point}" for point in synthesis.get("key_points", [])) or "- 暂无。"
    risks = "\n".join(f"- {risk}" for risk in synthesis.get("risks", [])) or "- 暂无。"
    actions = "\n".join(f"- [ ] {action}" for action in synthesis.get("next_actions", [])) or "- [ ] 人工核验来源。"
    notes = "\n".join(f"- {note}" for note in synthesis.get("suggested_notes", [])) or "- [[00_Inbox]]"
    return f"""# Web Research - {query}

> Generated by goldfish on {date_text}. This report uses only public pages. It does not log in, store cookies, bypass anti-scraping, or invent sources.

## Synthesis

{synthesis.get('answer', '')}

## Key Points

{key_points}

## Useful For Me

{synthesis.get('useful_for_me', '')}

## Risks And Checks

{risks}

## Next Actions

{actions}

## Suggested Note Locations

{notes}

## Search Results

{result_lines}

## Fetched Pages

{page_blocks}
"""


def save_research_report(query: str, markdown: str, root: Path | None = None) -> Path:
    root = root or kb_root()
    date_text = today_string()
    filename = safe_filename(f"WebResearch-{date_text}-{query}", 140) + ".md"
    return save_markdown(root / "04_Resources" / "AI-News" / "Reports" / filename, markdown)


class DuckDuckGoHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: List[Dict[str, Any]] = []
        self._in_result_link = False
        self._in_snippet = False
        self._current: Dict[str, Any] = {}
        self._buffer: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        classes = attr.get("class", "")
        if tag == "a" and ("result__a" in classes or "result-link" in classes):
            self._in_result_link = True
            self._buffer = []
            self._current = {"url": _clean_duckduckgo_url(attr.get("href", "")), "source": "DuckDuckGo HTML"}
        elif "result__snippet" in classes or "result-snippet" in classes:
            self._in_snippet = True
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._in_result_link or self._in_snippet:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_result_link:
            self._current["title"] = strip_html(" ".join(self._buffer)).strip()
            self._current.setdefault("snippet", "")
            if self._current.get("title") and self._current.get("url"):
                self.results.append(dict(self._current))
            self._in_result_link = False
            self._buffer = []
        elif self._in_snippet:
            snippet = strip_html(" ".join(self._buffer)).strip()
            if self.results and snippet:
                self.results[-1]["snippet"] = snippet
            self._in_snippet = False
            self._buffer = []


def _search_provider_order(provider: str | None = None) -> List[str]:
    requested = (provider or os.environ.get("GOLDFISH_SEARCH_PROVIDER") or "auto").strip().lower()
    aliases = {
        "brave-search": "brave",
        "brave_web": "brave",
        "ddg": "duckduckgo",
        "duck": "duckduckgo",
        "duckduckgo-html": "duckduckgo",
    }
    requested = aliases.get(requested, requested)
    if requested in {"brave", "duckduckgo"}:
        fallback = [item for item in ["duckduckgo"] if item != requested]
        return [requested, *fallback]
    order: List[str] = []
    if os.environ.get("BRAVE_SEARCH_API_KEY") or os.environ.get("BRAVE_API_KEY"):
        order.append("brave")
    order.append("duckduckgo")
    return order


def _fetch_json(url: str, timeout: int = 12, headers: Dict[str, str] | None = None) -> Dict[str, Any]:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    request_headers.update(headers or {})
    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset, errors="replace"))


def _brave_results_from_payload(payload: Dict[str, Any], limit: int = 6) -> List[Dict[str, Any]]:
    values = payload.get("web", {}).get("results", [])
    results = []
    for item in values[:limit]:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or item.get("profile", {}).get("url") or "").strip()
        title = str(item.get("title") or "").strip()
        if not url or not title:
            continue
        results.append(
            {
                "title": title,
                "url": url,
                "snippet": strip_html(str(item.get("description") or item.get("snippet") or "")).strip(),
                "source": "Brave Search",
            }
        )
    return results


def _clean_duckduckgo_url(url: str) -> str:
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    if "uddg" in query and query["uddg"]:
        return urllib.parse.unquote(query["uddg"][0])
    return urllib.parse.urljoin("https://duckduckgo.com", url)


def _is_fetchable_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    lowered = parsed.path.lower()
    return not lowered.endswith((".pdf", ".zip", ".tar", ".gz", ".mp4", ".mp3", ".png", ".jpg", ".jpeg", ".gif"))


def _is_search_result_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.netloc.endswith("duckduckgo.com"):
        return False
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path.startswith("/y.js"):
        return False
    if "ad_domain=" in parsed.query or "ad_provider=" in parsed.query:
        return False
    return True


def _page_block(index: int, page: Dict[str, Any]) -> str:
    content = truncate(page.get("content", ""), 1200)
    status = page.get("fetch_status", "")
    error = page.get("error", "")
    return f"""### {index}. {page.get('title', 'Untitled')}

- URL: {page.get('url', '')}
- Fetch status: {status}
- Error: {error or 'none'}

{content or page.get('snippet', '')}
"""


def _page_without_content(page: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in page.items() if key != "content"}


def _list_of_str(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []
