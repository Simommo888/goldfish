# Bing Search Skill

## Purpose

Use Bing Web Search as a public internet retrieval provider for goldfish research tasks.

## When To Use

Use this skill when the user asks for current web research, market scans, company/product discovery, competitor checks, or broad AI trend investigation and a Bing API key is available.

## Configuration

Set the API key with an environment variable:

```powershell
$env:BING_SEARCH_API_KEY="your-key"
```

Optional custom endpoint:

```powershell
$env:BING_SEARCH_ENDPOINT="https://api.bing.microsoft.com/v7.0/search"
```

To prefer Bing for a run:

```powershell
goldfish research "MCP server commercial opportunities" --search-provider bing
```

Inside chat:

```text
/research MCP server commercial opportunities --search-provider bing
```

## Operating Rules

1. Search public web pages only.
2. Do not log in.
3. Do not save cookies.
4. Do not bypass anti-scraping controls.
5. Treat snippets as discovery signals, not final evidence.
6. Fetch accessible public pages before summarizing claims.
7. If Bing is unavailable, allow fallback to DuckDuckGo/manual review.

## Output Expectations

Each result should preserve:

- title
- url
- snippet
- source: `Bing Web Search`
- fetched page status when available
- limitations or failed fetch reason
