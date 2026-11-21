# Collab config — yoru-manga-reader

## Stack
- Static site (GitHub Pages): `index.html`, `app.js` (vanilla JS), `styles.css`, `config.js`
- `library-data.js`: generated manifest (~1.6 MB) — images live on Cloudflare R2, not in Git
- Python 3 scripts (`scripts/generate_library.py`, `scripts/update-site.py`), PowerShell + rclone upload
- Docs/UI text are in Vietnamese — keep that language

## Commands
- Install: none (no package manager)
- Test (no test suite yet): `node --check app.js config.js && python3 -m py_compile scripts/*.py`
- Run/dev: `python3 -m http.server 8080` → http://localhost:8080/
- Regenerate manifest: `python3 scripts/generate_library.py` (needs local `library/`, gitignored)

## Roles (overrides global routing)
- lead: whoever the user is chatting with
- codex: Python scripts, app.js logic, syntax/smoke checks, reviewing every diff before merge
- agy: UI (index.html, styles.css, app.js rendering), README/SETUP docs, research

## Permissions
- codex: may edit (worktree, -w)
- agy: may edit (worktree, -w; file edits only)
- Never touch: `library-data.js` (generated — never hand-edit or regenerate in a worktree),
  `config.js` `assetBaseUrl`, `.env*`, `rclone.conf`, `library/`
- Never run: `git push`, `scripts/update-site.py` without `--generate-only`,
  `upload-library-to-r2.ps1 -Execute`, any rclone command (all publish/upload — user only)

## Project rules
- Done = test command above passes + page loads locally with no console errors (when UI changed)
- New logic in scripts should ship with a small check (e.g. `python3 -I` smoke run or doctest)
- Keep it dependency-free: no npm/pip packages, no build step
- Don't load `library-data.js` into context; inspect with `head -c` / a script if needed

## Collaboration
- Lead plans, routes, checks results; steps in only when really needed (both teammates blocked,
  fix-up rounds used up, or tiny task) and says why.
- Blocked teammate: give the cause + a workaround and try it; `NEEDS USER:` for steps only the
  user can do (R2 upload, push, rclone config); `SUGGEST codex|agy:` when the other teammate has a better tool.
- agy edits UI → codex runs the test command and reviews the diff before merge.
