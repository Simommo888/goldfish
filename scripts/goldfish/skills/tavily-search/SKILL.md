# Tavily Search Skill

## Purpose

Use Tavily Search API as goldfish's primary public internet retrieval provider.

## When To Use

Use this skill for AI market scans, current topic research, startup/product discovery, Agent/RAG/MCP research, and other tasks where an agent-friendly search API is useful.

## Configuration

Set the API key with an environment variable:

```powershell
$env:TAVILY_API_KEY="your-key"
```

Optional custom endpoint:

```powershell
$env:TAVILY_SEARCH_ENDPOINT="https://api.tavily.com/search"
```

Make Tavily the default provider:

```powershell
$env:GOLDFISH_SEARCH_PROVIDER="tavily"
```

Run a Tavily-backed research query:

```powershell
goldfish research "MCP server commercial opportunities" --search-provider tavily
```

Inside chat:

```text
/research MCP server commercial opportunities --search-provider tavily
```

## Operating Rules

1. Search public web pages only.
2. Do not log in.
3. Do not save cookies.
4. Do not bypass anti-scraping controls.
5. Treat snippets as discovery signals, not final evidence.
6. Fetch accessible public pages before summarizing claims.
7. If Tavily is unavailable, allow fallback to Jina, then DuckDuckGo/manual review.

## Output Expectations

Each result should preserve:

- title
- url
- snippet
- source: `Tavily Search`
- fetched page status when available
- limitations or failed fetch reason
