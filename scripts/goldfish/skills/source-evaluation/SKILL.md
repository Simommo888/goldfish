# Source Evaluation Skill

## Purpose

Judge whether a source is reliable, relevant, fresh, and worth using in goldfish reports or research.

## When To Use

Use this skill when adding sources, deciding whether to trust a search result, reviewing source health, or diagnosing low-quality retrieval.

## Evaluation Criteria

- Public accessibility
- Originality: primary source, official source, paper, repository, or credible reporting
- Relevance to the user's focus areas
- Update frequency
- Signal-to-noise ratio
- Citation or evidence quality
- Failure rate
- Manual review burden
- Risk of hype, gossip, rumor, or private-life content

## Priority Guide

- Priority 5: official model/product/research source, top paper feed, high-signal repository source
- Priority 4: credible specialist blog, strong technical newsletter, trustworthy benchmark source
- Priority 3: useful aggregator with links to primary sources
- Priority 2: noisy but occasionally useful source
- Priority 1: manual-only or low-confidence source
- Disable: repeated failures, private/gossip focus, login-only, or unverifiable claims

## Output Shape

Return:

- `source_name`
- `keep_or_change`
- `priority`
- `trust_level`
- `failure_risk`
- `evidence_quality`
- `reason`
- `recommended_config_change`
