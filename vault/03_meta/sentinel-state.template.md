# Sentinel state (template)

Copy this file to `sentinel-state.md` on first setup (same folder).
`sentinel-state.md` is gitignored — it is machine-specific.

```yaml
last_commit: ""
last_checked: ""
code_repo: "/absolute/path/to/your/work/codebase"
branch: "main"
```

The weekly `kb-sentinel-check` playbook reads and overwrites `sentinel-state.md`.
Point `code_repo` at the application you document — usually NOT this RAGgamuffin
repo itself, but the Laravel/project repo at work.
