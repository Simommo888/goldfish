# Internet Search Provider Skill

## Purpose

Choose the best public web search provider for goldfish research goals.

## Provider Priority

Use `auto` by default:

1. Brave Search API if `BRAVE_SEARCH_API_KEY` or `BRAVE_API_KEY` exists.
2. DuckDuckGo HTML fallback when no API provider is configured.

The user can force a provider with:

```powershell
goldfish research "query" --search-provider brave
goldfish research "query" --search-provider duckduckgo
```

## Selection Guidance

- Use Brave for broad current web research, market scans, product lists, competitor discovery, Agent/RAG/MCP topics, and general source discovery.
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

- `GOLDFISH_SEARCH_PROVIDER`: optional default provider, one of `auto`, `brave`, `duckduckgo`.
- `BRAVE_SEARCH_API_KEY`: Brave Search API key.
- `BRAVE_SEARCH_ENDPOINT`: optional Brave endpoint.

## Output Shape

Research outputs should include:

- provider used
- query
- result count
- fetched page count
- source titles and URLs
- failed fetch reasons
- synthesis based only on provided sources
