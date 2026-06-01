"""Public web research for goldfish.

Safety boundary: this module only uses public search result pages and public
web pages. It does not log in, store cookies, bypass anti-scraping protections,
or crawl unbounded link graphs.
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List
from urllib.request import Request, urlopen

from .providers.registry import get_provider, resolve_llm_connection
from .storage import save_markdown
from .utils import USER_AGENT, fetch_url, get_env, kb_root, now, safe_filename, strip_html, today_string, truncate


SEARCH_URLS = [
    "https://lite.duckduckgo.com/lite/?q={query}",
    "https://duckduckgo.com/html/?q={query}",
]
GDELT_DOC_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
HACKERNEWS_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"
MAX_PAGE_CHARS = 6000


def research_public_web(
    query: str,
    limit: int = 6,
    fetch_limit: int = 4,
    timeout: int = 12,
    use_llm: bool = True,
    save: bool = True,
    search_provider: str | None = None,
    timespan: str | None = None,
    root: Path | None = None,
) -> Dict[str, Any]:
    root = root or kb_root()
    query = query.strip()
    if not query:
        return {"query": query, "error": "query is required", "results": [], "pages": []}

    search_results = search_public_web(query, limit=limit, timeout=timeout, provider=search_provider, timespan=timespan)
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


def search_public_web(
    query: str,
    limit: int = 6,
    timeout: int = 12,
    provider: str | None = None,
    timespan: str | None = None,
) -> List[Dict[str, Any]]:
    errors = []
    attempted = []
    for search_provider in _search_provider_order(provider):
        attempted.append(search_provider)
        try:
            if search_provider == "tavily":
                results = search_tavily_web(query, limit=limit, timeout=timeout)
            elif search_provider == "jina":
                results = search_jina_web(query, limit=limit, timeout=timeout)
            elif search_provider == "hackernews":
                results = search_hackernews_web(query, limit=limit, timeout=timeout)
            elif search_provider == "gdelt":
                results = search_gdelt_news(query, limit=limit, timeout=timeout, timespan=timespan)
            else:
                results = search_duckduckgo_html(query, limit=limit, timeout=timeout)
            if results:
                for result in results:
                    result.setdefault("provider_order", " -> ".join(attempted))
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


def search_tavily_web(query: str, limit: int = 6, timeout: int = 12) -> List[Dict[str, Any]]:
    api_key = get_env("TAVILY_API_KEY")
    endpoint = get_env("TAVILY_SEARCH_ENDPOINT", "https://api.tavily.com/search").rstrip("/")
    if not api_key:
        raise RuntimeError("missing TAVILY_API_KEY")
    payload = _post_json(
        endpoint,
        {
            "query": query,
            "search_depth": os.environ.get("TAVILY_SEARCH_DEPTH", "basic"),
            "max_results": max(1, min(limit, 20)),
            "include_answer": False,
            "include_raw_content": False,
        },
        timeout=timeout,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    return _tavily_results_from_payload(payload, limit=limit)


def search_jina_web(query: str, limit: int = 6, timeout: int = 12) -> List[Dict[str, Any]]:
    api_key = get_env("JINA_API_KEY") or get_env("JINA_SEARCH_API_KEY")
    endpoint = get_env("JINA_SEARCH_ENDPOINT", "https://s.jina.ai/").rstrip("/")
    if not api_key:
        raise RuntimeError("missing JINA_API_KEY")
    url = endpoint + "?" + urllib.parse.urlencode({"q": query})
    text = _fetch_text(url, timeout=timeout, headers={"Authorization": f"Bearer {api_key}", "Accept": "text/plain"})
    return _jina_results_from_text(text, limit=limit)


def search_hackernews_web(query: str, limit: int = 6, timeout: int = 12) -> List[Dict[str, Any]]:
    url = HACKERNEWS_SEARCH_URL + "?" + urllib.parse.urlencode({"query": query, "tags": "story", "hitsPerPage": max(1, min(limit, 50))})
    payload = _fetch_json(url, timeout=timeout, headers={"Accept": "application/json"})
    return _hackernews_results_from_payload(payload, limit=limit)


def search_gdelt_news(query: str, limit: int = 6, timeout: int = 12, timespan: str | None = None) -> List[Dict[str, Any]]:
    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": max(1, min(limit, 50)),
    }
    if timespan:
        params["timespan"] = timespan
    url = GDELT_DOC_API_URL + "?" + urllib.parse.urlencode(params)
    payload = _fetch_json(url, timeout=timeout, headers={"Accept": "application/json"})
    return _gdelt_results_from_payload(payload, limit=limit)


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
    requested = (provider or get_env("GOLDFISH_SEARCH_PROVIDER", "auto") or "auto").strip().lower()
    aliases = {
        "tavily-search": "tavily",
        "tavily_web": "tavily",
        "jina-search": "jina",
        "jina_web": "jina",
        "hn": "hackernews",
        "hacker-news": "hackernews",
        "algolia": "hackernews",
        "news": "news",
        "latest": "news",
        "realtime": "news",
        "real-time": "news",
        "ddg": "duckduckgo",
        "duck": "duckduckgo",
        "duckduckgo-html": "duckduckgo",
        "gdelt-doc": "gdelt",
    }
    requested = aliases.get(requested, requested)
    if requested == "news":
        order: List[str] = []
        if get_env("TAVILY_API_KEY"):
            order.append("tavily")
        if get_env("JINA_API_KEY") or get_env("JINA_SEARCH_API_KEY"):
            order.append("jina")
        return [*order, "hackernews", "gdelt", "duckduckgo"]
    if requested in {"tavily", "jina", "hackernews", "gdelt", "duckduckgo"}:
        if requested == "tavily":
            return ["tavily", "jina", "hackernews", "gdelt", "duckduckgo"]
        if requested == "jina":
            return ["jina", "hackernews", "gdelt", "duckduckgo"]
        if requested == "hackernews":
            return ["hackernews", "gdelt", "duckduckgo"]
        if requested == "gdelt":
            return ["gdelt", "hackernews", "duckduckgo"]
        return ["duckduckgo"]
    order: List[str] = []
    if get_env("TAVILY_API_KEY"):
        order.append("tavily")
    if get_env("JINA_API_KEY") or get_env("JINA_SEARCH_API_KEY"):
        order.append("jina")
    order.append("duckduckgo")
    return order


def _fetch_text(url: str, timeout: int = 12, headers: Dict[str, str] | None = None) -> str:
    request_headers = {"User-Agent": USER_AGENT}
    request_headers.update(headers or {})
    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _fetch_json(url: str, timeout: int = 12, headers: Dict[str, str] | None = None) -> Dict[str, Any]:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    request_headers.update(headers or {})
    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset, errors="replace"))


def _post_json(url: str, payload: Dict[str, Any], timeout: int = 12, headers: Dict[str, str] | None = None) -> Dict[str, Any]:
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json", "Content-Type": "application/json"}
    request_headers.update(headers or {})
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers=request_headers, method="POST")
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return json.loads(response.read().decode(charset, errors="replace"))


def _tavily_results_from_payload(payload: Dict[str, Any], limit: int = 6) -> List[Dict[str, Any]]:
    values = payload.get("results", [])
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
                "snippet": strip_html(str(item.get("content") or item.get("snippet") or "")).strip(),
                "source": "Tavily Search",
            }
        )
    return results


def _jina_results_from_text(text: str, limit: int = 6) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    current: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        lower = line.lower()
        if lower.startswith("title:"):
            if current.get("title") and current.get("url"):
                results.append(_jina_result(current))
                current = {}
            current["title"] = line.split(":", 1)[1].strip()
            continue
        if lower.startswith("url source:") or lower.startswith("url:") or lower.startswith("source:"):
            value = line.split(":", 1)[1].strip()
            if value.startswith("http"):
                current["url"] = value
            continue
        if lower.startswith("description:") or lower.startswith("content:") or lower.startswith("snippet:"):
            current["snippet"] = line.split(":", 1)[1].strip()
            continue
        if line.startswith("http") and "url" not in current:
            current["url"] = line
            continue
        if current.get("title") and "snippet" not in current and not line.startswith("#"):
            current["snippet"] = line
    if current.get("title") and current.get("url"):
        results.append(_jina_result(current))
    if not results:
        results = _jina_markdown_link_results(text)
    return results[:limit]


def _jina_result(value: Dict[str, str]) -> Dict[str, str]:
    return {
        "title": strip_html(value.get("title", "")).strip(),
        "url": value.get("url", "").strip(),
        "snippet": strip_html(value.get("snippet", "")).strip(),
        "source": "Jina Search",
    }


def _jina_markdown_link_results(text: str) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    for title, url in re.findall(r"\[([^\]]+)\]\((https?://[^)]+)\)", text):
        results.append({"title": strip_html(title), "url": url, "snippet": "", "source": "Jina Search"})
    return results


def _hackernews_results_from_payload(payload: Dict[str, Any], limit: int = 6) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for hit in payload.get("hits", []):
        title = str(hit.get("title") or hit.get("story_title") or "").strip()
        url = str(hit.get("url") or "").strip()
        object_id = str(hit.get("objectID") or hit.get("story_id") or "").strip()
        if not url and object_id:
            url = f"https://news.ycombinator.com/item?id={object_id}"
        if not title or not url:
            continue
        created_at = str(hit.get("created_at") or "").strip()
        points = hit.get("points")
        comments = hit.get("num_comments")
        snippet_parts = []
        if created_at:
            snippet_parts.append(f"published: {created_at}")
        if points is not None:
            snippet_parts.append(f"points: {points}")
        if comments is not None:
            snippet_parts.append(f"comments: {comments}")
        results.append(
            {
                "title": strip_html(title),
                "url": url,
                "snippet": "; ".join(snippet_parts),
                "source": "Hacker News Algolia",
                "published": created_at,
            }
        )
        if len(results) >= limit:
            break
    return results


def _gdelt_results_from_payload(payload: Dict[str, Any], limit: int = 6) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for article in payload.get("articles", []):
        title = str(article.get("title") or "").strip()
        url = str(article.get("url") or "").strip()
        if not title or not url:
            continue
        domain = str(article.get("domain") or "").strip()
        seendate = str(article.get("seendate") or "").strip()
        country = str(article.get("sourcecountry") or "").strip()
        language = str(article.get("language") or "").strip()
        snippet = "; ".join(part for part in [domain, language, country, seendate] if part)
        results.append(
            {
                "title": strip_html(title),
                "url": url,
                "snippet": snippet,
                "source": "GDELT DOC API",
                "published": seendate,
            }
        )
        if len(results) >= limit:
            break
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
