# Jina Search Skill

## Purpose

Use Jina Search as goldfish's secondary public internet retrieval provider and LLM-readable search fallback.

## When To Use

Use this skill when Tavily is unavailable, when search output should be easy for an LLM to read, or when the task benefits from web-to-text oriented search.

## Configuration

Set the API key with an environment variable:

```powershell
$env:JINA_API_KEY="your-key"
```

Fallback variable name:

```powershell
$env:JINA_SEARCH_API_KEY="your-key"
```

Optional endpoint:

```powershell
$env:JINA_SEARCH_ENDPOINT="https://s.jina.ai/"
```

Run a Jina-backed research query:

```powershell
goldfish research "AI coding agent market" --search-provider jina
```

Inside chat:

```text
/research AI coding agent market --search-provider jina
```

## Operating Rules

1. Search public web pages only.
2. Do not log in.
3. Do not save cookies.
4. Do not bypass anti-scraping controls.
5. Treat search text as source discovery until pages are fetched.
6. If Jina is unavailable, allow fallback to DuckDuckGo/manual review.

## Output Expectations

Each result should preserve:

- title
- url
- snippet
- source: `Jina Search`
- fetched page status when available
- limitations or failed fetch reason
