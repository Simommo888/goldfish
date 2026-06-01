# Query Expansion Skill

## Purpose

Generate precise search queries for AI intelligence retrieval without drifting away from the user's goal.

## When To Use

Use this skill when the initial question is broad, ambiguous, multilingual, or likely to miss important results with a single query.

## Query Rules

1. Preserve the user's original intent.
2. Create both broad and narrow queries.
3. Include synonyms, product names, project names, and technical terms.
4. Add time-sensitive terms only when recency matters.
5. Include source-specific queries when needed.
6. Avoid gossip, private life, rumor, fan disputes, or unsupported claims.
7. Prefer English queries for global AI sources; add Chinese queries only when China-specific sources matter.

## Query Families

- Primary concept query
- Technical mechanism query
- Product or vendor query
- Open-source query
- Research or paper query
- Business or market query
- Risk or criticism query
- Local knowledge-base query

## Output Shape

Return:

- `core_query`
- `expanded_queries`
- `source_specific_queries`
- `local_search_queries`
- `negative_terms`
- `why_these_queries`
