# Fact Checking Skill

## Purpose

Check whether a proposed answer or research finding is supported by public evidence before goldfish writes it into reports or notes.

## When To Use

Use this skill before final answers, trend claims, business conclusions, or permanent notes when claims may be outdated, controversial, or source-dependent.

## Verification Rules

1. Identify factual claims.
2. Link each claim to evidence.
3. Prefer primary sources.
4. Cross-check important claims across at least two sources when possible.
5. Mark uncertain claims as uncertain.
6. Remove unsupported claims.
7. Do not invent dates, metrics, quotes, or opinions.

## Claim Labels

- `verified`
- `partially_supported`
- `uncertain`
- `unsupported`
- `out_of_scope`

## Output Shape

Return:

- `claim`
- `status`
- `supporting_sources`
- `contradicting_sources`
- `confidence`
- `safe_wording`
- `should_include`
