# Retrieval Planning Skill

## Purpose

Turn a vague information need into a bounded retrieval plan that goldfish can execute with public web research, local search, source review, and knowledge deposition tools.

## When To Use

Use this skill before research when the user asks to investigate, compare, monitor, understand a market, find evidence, or answer a question that needs sources.

## Operating Rules

1. Clarify the target question in one sentence.
2. Split the task into subquestions.
3. Decide whether to use public web search, local search, source health, daily run, or memory.
4. Prefer authoritative and primary sources first.
5. Keep the plan short: 3 to 7 steps.
6. Do not request private data, login-only pages, cookies, or anti-scraping bypass.
7. Define what counts as enough evidence before synthesizing.

## Retrieval Plan Template

- Goal
- Scope
- Subquestions
- Source classes
- Search queries
- Evidence threshold
- Tools to call
- Stop condition
- Expected output

## Tool Preference

- Use `web_search` for public web search and research-mode investigation.
- Use `search` for previous notes, reports, local memory, or generated drafts.
- Use `source_health` when source reliability is part of the task.
- Use `doctor` only when runtime or API health is suspected.

## Output Shape

Return:

- `research_question`
- `scope`
- `queries`
- `source_priority`
- `tool_plan`
- `evidence_threshold`
- `risks`
- `next_action`
