# Evidence Capture Skill

## Purpose

Convert raw search and fetch results into clean, auditable evidence records that can support summaries, reports, and permanent notes.

## When To Use

Use this skill after web research, RSS collection, paper fetching, or local search when information needs to be summarized without losing traceability.

## Capture Rules

1. Every important claim needs a source URL.
2. Do not mix source facts with the agent's interpretation.
3. Preserve publication dates when available.
4. Record fetch failures and manual-review items.
5. Truncate long content but keep enough context to verify.
6. Mark confidence explicitly.
7. Never fabricate missing metadata.

## Evidence Record

- `claim`
- `source_title`
- `source_url`
- `source_type`
- `published_at`
- `fetched_at`
- `supporting_detail`
- `confidence`: high / medium / low
- `needs_manual_review`
- `notes`

## Output Shape

Return:

- `evidence_records`
- `strongest_sources`
- `weak_or_missing_evidence`
- `manual_review_items`
- `safe_summary_inputs`
