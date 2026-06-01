# Google Search Skill

## Purpose

Use Google Custom Search as a public internet retrieval provider for precise source discovery.

## When To Use

Use this skill when the user asks for technical docs, exact product pages, source verification, site-restricted research, or high-precision public web lookup and Google Custom Search credentials are available.

## Configuration

Set credentials with environment variables:

```powershell
$env:GOOGLE_SEARCH_API_KEY="your-key"
$env:GOOGLE_SEARCH_CX="your-programmable-search-engine-cx"
```

Fallback variable names are also supported:

```powershell
$env:GOOGLE_API_KEY="your-key"
$env:GOOGLE_CSE_ID="your-cx"
```

To prefer Google for a run:

```powershell
goldfish research "RAG evaluation framework docs" --search-provider google
```

Inside chat:

```text
/research RAG evaluation framework docs --search-provider google
```

## Operating Rules

1. Search public web pages only.
2. Do not log in.
3. Do not save cookies.
4. Do not bypass anti-scraping controls.
5. Treat search snippets as leads, not evidence.
6. Fetch public pages before summarizing.
7. If Google credentials are missing or the API fails, allow fallback to DuckDuckGo/manual review.

## Output Expectations

Each result should preserve:

- title
- url
- snippet
- source: `Google Custom Search`
- fetched page status when available
- limitations or failed fetch reason
