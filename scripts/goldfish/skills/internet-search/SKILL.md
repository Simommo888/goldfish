# Internet Search Provider Skill

## Purpose

Choose the best public web search provider for goldfish research goals.

## Provider Priority

Use `auto` by default:

1. Bing Web Search if `BING_SEARCH_API_KEY` or `AZURE_BING_SEARCH_KEY` exists.
2. Google Custom Search if `GOOGLE_SEARCH_API_KEY` and `GOOGLE_SEARCH_CX` exist.
3. DuckDuckGo HTML fallback when no API provider is configured.

The user can force a provider with:

```powershell
goldfish research "query" --search-provider bing
goldfish research "query" --search-provider google
goldfish research "query" --search-provider duckduckgo
```

## Selection Guidance

- Use Bing for broad current web research, market scans, product lists, and competitor discovery.
- Use Google for precise source discovery, technical docs, site-specific searches, and verification.
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

- `GOLDFISH_SEARCH_PROVIDER`: optional default provider, one of `auto`, `bing`, `google`, `duckduckgo`.
- `BING_SEARCH_API_KEY`: Bing Web Search key.
- `BING_SEARCH_ENDPOINT`: optional Bing endpoint.
- `GOOGLE_SEARCH_API_KEY`: Google API key.
- `GOOGLE_SEARCH_CX`: Google Programmable Search Engine cx id.

## Output Shape

Research outputs should include:

- provider used
- query
- result count
- fetched page count
- source titles and URLs
- failed fetch reasons
- synthesis based only on provided sources
