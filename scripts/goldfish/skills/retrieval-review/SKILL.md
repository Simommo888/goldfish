# Retrieval Review Skill

## Purpose

Review the quality of a completed retrieval run and decide what should be improved before the result is trusted.

## When To Use

Use this skill after `web_search`, `agent`, daily runs, or source-health reviews.

## Review Checklist

- Did the search query match the user's goal?
- Were enough source types checked?
- Were primary sources included?
- Were inaccessible sources marked manual review?
- Did any claim lack evidence?
- Was the output too broad or too narrow?
- Were private, gossip, login-only, or anti-scraping sources avoided?
- Should sources be added, disabled, or reprioritized?

## Quality Levels

- `high`: multiple relevant public sources, primary evidence, clear answer
- `medium`: useful but missing some primary sources or dates
- `low`: mostly snippets, weak sources, broad query, or many manual review items
- `failed`: no useful evidence or tool failure

## Output Shape

Return:

- `quality_level`
- `what_worked`
- `gaps`
- `source_changes`
- `query_changes`
- `followup_research`
- `safe_to_write_notes`
