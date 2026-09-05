# Contributing to the docs

The documentation site is **MkDocs + Material**, configured at the repo root in
`mkdocs.yml`. It surfaces the existing Markdown in `docs/` as-is — there is no
duplicated content. Published to GitHub Pages by `.github/workflows/docs.yml` on
every push to `main`.

## Run it locally

The docs toolchain is independent of the `api/` package, so use its own venv:

```bash
python -m venv .venv-docs
# Windows PowerShell:  .venv-docs\Scripts\Activate.ps1
# Windows Git Bash:    source .venv-docs/Scripts/activate
# macOS / Linux:       source .venv-docs/bin/activate
pip install -r docs/requirements.txt

mkdocs serve          # live-reload preview at http://127.0.0.1:8000
```

## Before you push

```bash
mkdocs build --strict     # fails on broken links or pages missing from the nav
```

CI runs the same `--strict` build, so a green local build is the gate.

## Adding a page

1. Add the Markdown file under `docs/`.
2. Add it to the `nav:` tree in `mkdocs.yml` — `--strict` fails on any `docs/`
   page that is not in the nav.
3. Use relative links between docs pages (e.g. `[Roadmap](ROADMAP.md)`), not
   `docs/`-prefixed paths.

## Notes

- `.venv-docs/` is git-ignored (covered by the `.venv*` / `venv/` rules).
- Mermaid code fences render natively via the Material `superfences` config.
- The `site_url` / `repo_url` slug in `mkdocs.yml` still points at a placeholder
  org — update it once the GitHub repo exists (see [Status](STATUS.md)).
