# Internet Search Provider Skill

## Purpose

Choose the best public web search provider for goldfish research goals.

## Provider Priority

Use `auto` by default:

1. Tavily Search API if `TAVILY_API_KEY` exists.
2. Jina Search if `JINA_API_KEY` or `JINA_SEARCH_API_KEY` exists.
3. Realtime News Chain for latest/today/realtime queries.
4. Hacker News Algolia for no-key developer news.
5. GDELT DOC API for no-key global news fallback.
6. DuckDuckGo HTML fallback when no API provider is configured.

The user can force a provider with:

```powershell
goldfish research "query" --search-provider tavily
goldfish research "query" --search-provider jina
goldfish web "query" --search-provider news
goldfish web "query" --search-provider hackernews
goldfish web "query" --search-provider gdelt
goldfish research "query" --search-provider duckduckgo
```

## Selection Guidance

- Use Tavily for agentic web research, market scans, product lists, competitor discovery, Agent/RAG/MCP topics, and general source discovery.
- Use Jina for LLM-readable search output, web-to-text research, and backup retrieval.
- Use News mode for "latest", "today", "realtime", "最新", "实时", or "新闻" queries.
- Use Hacker News for current developer and AI engineering links.
- Use GDELT for broad global media monitoring when API keys are unavailable.
- Use DuckDuckGo when no API keys are configured or when the user wants a no-key fallback.

## Safety Rules

1. Use public web pages only.
2. Do not log in.
3. Do not bypass anti-scraping controls.
4. Do not store cookies.
5. Do not treat snippets as proof.
6. Do not invent sources when a provider fails.
7. Mark inaccessible or failed pages as manual review.

## Environment Variables

- `GOLDFISH_SEARCH_PROVIDER`: optional default provider, one of `auto`, `news`, `tavily`, `jina`, `hackernews`, `gdelt`, `duckduckgo`.
- `TAVILY_API_KEY`: Tavily Search API key.
- `TAVILY_SEARCH_ENDPOINT`: optional Tavily endpoint.
- `JINA_API_KEY`: Jina API key.
- `JINA_SEARCH_ENDPOINT`: optional Jina endpoint.

## Output Shape

Research outputs should include:

- provider used
- query
- result count
- fetched page count
- source titles and URLs
- failed fetch reasons
- synthesis based only on provided sources
