# Source Curation Skill

## Purpose

Help goldfish maintain high-quality public AI intelligence sources.

## When To Use

Use this skill when the user asks to add, remove, evaluate, prioritize, or repair AI news, paper, product, open-source, or people-watch sources.

## Operating Rules

1. Only use public sources.
2. Do not use sources that require login, cookies, private groups, or anti-scraping bypass.
3. Prefer stable RSS or Atom feeds.
4. If a source has no stable RSS, mark it as manual review.
5. Every new source must have a clear reason.
6. Disable or replace sources that repeatedly fail or produce low-value items.

## Source Evaluation Checklist

- Source name
- Category
- Public URL
- RSS URL if available
- Expected update frequency
- Relevance to Agent, RAG, AI Coding, MCP, knowledge base, AI products, or AI business
- Trust level
- Failure risk
- Why it belongs in goldfish

## Output Shape

For each recommendation, provide:

- `action`: add / keep / lower_priority / raise_priority / disable / replace
- `source_name`
- `reason`
- `suggested_priority`
- `rss_url`
- `notes`
