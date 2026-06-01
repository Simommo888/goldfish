# Brave Search Skill

## Purpose

Use Brave Search API as the primary public internet retrieval provider for goldfish research tasks.

## When To Use

Use this skill for current web research, AI market scans, startup/product discovery, competitor checks, Agent/RAG/MCP research, and source discovery when a Brave API key is available.

## Configuration

Set the API key with an environment variable:

```powershell
$env:BRAVE_SEARCH_API_KEY="your-key"
```

Optional custom endpoint:

```powershell
$env:BRAVE_SEARCH_ENDPOINT="https://api.search.brave.com/res/v1/web/search"
```

Make Brave the default provider:

```powershell
$env:GOLDFISH_SEARCH_PROVIDER="brave"
```

Run a Brave-backed research query:

```powershell
goldfish research "MCP server commercial opportunities" --search-provider brave
```

Inside chat:

```text
/research MCP server commercial opportunities --search-provider brave
```

## Operating Rules

1. Search public web pages only.
2. Do not log in.
3. Do not save cookies.
4. Do not bypass anti-scraping controls.
5. Treat snippets as discovery signals, not final evidence.
6. Fetch accessible public pages before summarizing claims.
7. If Brave is unavailable, allow fallback to DuckDuckGo/manual review.

## Output Expectations

Each result should preserve:

- title
- url
- snippet
- source: `Brave Search`
- fetched page status when available
- limitations or failed fetch reason
