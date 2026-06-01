# Web Research Skill

## Purpose

Guide goldfish through public web research with source-aware collection, bounded fetching, and evidence-first notes.

## When To Use

Use this skill for public internet research, market scans, product comparisons, technical landscape reviews, and current AI topic investigation.

## Safety Rules

1. Use public pages only.
2. Do not log in.
3. Do not bypass paywalls or anti-scraping controls.
4. Do not save cookies.
5. Do not treat snippets as full evidence when page fetch failed.
6. Mark inaccessible pages as manual review.
7. Do not invent sources or claims.

## Research Flow

1. Start with a retrieval plan.
2. Generate 3 to 8 queries.
3. Select a public search provider:
   - `auto` by default.
   - `tavily` when Tavily credentials are available and agentic search quality matters.
   - `jina` when LLM-readable search output or backup retrieval is useful.
   - `duckduckgo` as the no-key fallback.
4. Fetch only accessible pages.
5. Extract title, URL, date, publisher, core claim, and useful quotes or paraphrases.
6. Group evidence by theme.
7. Separate facts, inference, and speculation.
8. Produce a Markdown research note.

## Provider Commands

```powershell
goldfish research "MCP server commercial opportunities" --search-provider auto
goldfish research "MCP server commercial opportunities" --search-provider tavily
goldfish research "AI coding agent market" --search-provider jina
goldfish research "AI coding agent market" --search-provider duckduckgo
```

## Evidence Fields

- title
- url
- source_type
- publisher
- published_at
- fetched_at
- claim
- evidence_summary
- confidence
- limitations

## Output Shape

Return:

- `question`
- `sources_checked`
- `evidence`
- `findings`
- `uncertainties`
- `recommended_followups`
- `suggested_note_locations`
