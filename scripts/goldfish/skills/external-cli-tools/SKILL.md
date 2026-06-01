# External CLI Tools Skill

## Purpose

Let goldfish use local command-line tools as bounded, allow-listed capabilities.

## When To Use

Use this skill when the user asks goldfish to call local tools such as ripgrep, git, Python, Go, Node, Chafa, or future CLI utilities.

## Safety Rules

1. Only run tools declared in `scripts/goldfish/config/external_tools.json`.
2. Do not run arbitrary user-provided shell strings.
3. Prefer `runner: direct` over `runner: bash`.
4. Keep working directories inside the project unless the config explicitly allows more.
5. Redact API keys and secrets from command output.
6. Truncate long output.
7. Use `dry_run` before enabling mutating tools.
8. Do not add destructive tools without a clear user decision.

## CLI Usage

```powershell
goldfish external list
goldfish external run rg_search query=MCP path=scripts/goldfish
goldfish external run git_status
goldfish external run git_log limit=5
goldfish external run rg_search query=Agent path=scripts/goldfish --dry-run
```

## Chat Usage

```text
/external
/exec rg_search query=MCP path=scripts/goldfish
/exec git_status
```

## Output Shape

Return:

- `tool_name`
- `runner`
- `cwd`
- `command`
- `exit_code`
- `stdout`
- `stderr`
- `status`
