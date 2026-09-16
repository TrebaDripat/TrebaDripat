# GameBoy RPG Profile README — Design

Date: 2026-09-16 · Repo: `TrebaDripat/TrebaDripat`

## Goal

Replace the current "stylish" README with a profile that reads as a handheld
RPG screen: fun to browse, visibly alive (animation + daily-refreshed data),
and honest about private projects (no dead links).

## Constraints (GitHub README)

- No JS/CSS in Markdown. Only: Markdown, limited HTML, `<details>`, `<img>`.
- SVGs loaded via `<img>` DO run CSS/SMIL animations; they do NOT run scripts
  or load external fonts/images. Fonts must be embedded (base64).
- Camo proxy caches images; cache-busting is not needed for daily updates
  (GitHub purges on file change in the repo).

## Visual system

- Palette (GameBoy DMG): `#0f380f` (darkest), `#306230`, `#8bac0f`, `#9bbc0f`
  (lightest). Screen bezel `#c4bebb`, shadow `#8b8b8b`. Accent for the
  Ukrainian flag only: `#0057b7` / `#ffd700`.
- Font: **Press Start 2P** (OFL), embedded as base64 WOFF2 in each SVG.
- All shapes on an integer 4px grid; `shape-rendering="crispEdges"`.
- Each SVG has its own opaque background so it looks identical in light and
  dark GitHub themes.
- Width 800px, `viewBox` fixed, responsive via `width="100%"` in README.

## Screens (README order)

| # | Screen | File | Source of data | Animation |
|---|--------|------|----------------|-----------|
| 1 | Title | `assets/title.svg` | static | `PRESS START` blink; hero 2-frame idle; flag wave |
| 2 | Dialogue | `assets/dialogue.svg` | static | 4 lines typed sequentially, cursor blink, loop |
| 3 | Character sheet | `assets/charsheet.svg` | **generated** | HP/MP/XP bars fill-in on load |
| 4 | Inventory | `assets/inventory.svg` | static | selected-slot cursor bounces |
| 5 | Quest log | Markdown `<details>` | static | none (native disclosure) |
| 6 | World map | `assets/worldmap.svg` | **generated** | hero idle on "today" tile |
| 7 | Save & Continue | Markdown | static | none |

### 3. Character sheet — formulas

- `total_commits` = sum of `contributionsCollection.totalCommitContributions`
  over each year since account creation (GraphQL, includes private repos
  when the token owner is the profile owner).
- `LVL = floor(sqrt(total_commits / 10))`, minimum 1.
- `XP` bar = progress inside current level: `(total_commits - 10*LVL^2) /
  (10*(LVL+1)^2 - 10*LVL^2)`.
- `HP` = public + private repos count (capped at bar width, label shows raw).
- `MP` = followers.
- `PLAYTIME` = years and months since `created_at`.
- Stat bars `PY / TS / 3D / INFRA` = hand-set 0–10 constants in
  `scripts/profile_config.json` (self-assessment, not derived).

### 6. World map — mapping

- Fetch last 53 weeks of `contributionCalendar` (7×53 grid).
- Tile per day by contribution count: 0 → water/plain, 1–2 → grass, 3–5 →
  forest, 6–9 → hills, 10+ → mountain. Rendered as 12px tiles.
- Hero sprite on the last (today) cell. Legend below.

## Quest log content

Six quests, each a `<details>` with: status badge (`🔒 LOCKED` for private,
`✅ CLEARED` for public), one-line pitch, 3 bullets, `REWARDS:` line listing
skills gained. No links to private repos. Public ones may link.

## Generation pipeline

- `scripts/build_assets.py` (Python 3.12, stdlib + `requests`):
  1. Query GitHub GraphQL with `GITHUB_TOKEN`.
  2. Compute numbers per formulas above.
  3. Render `charsheet.svg` and `worldmap.svg` from string templates in
     `scripts/templates/`.
  4. Write only if content changed.
- `.github/workflows/update-profile.yml`: `schedule: '17 3 * * *'` +
  `workflow_dispatch`; permissions `contents: write`; commits as
  `github-actions[bot]` with message `chore: refresh profile assets`.
- Static SVGs (title, dialogue, inventory) are hand-authored and committed;
  the script never touches them.

## Error handling

- API failure → script exits non-zero, workflow fails, previous SVGs remain
  (README never shows a broken image).
- Missing font file → build aborts with a clear message.

## Testing / verification

1. Open each SVG in the Browser pane; confirm animation plays and pixels are
   crisp.
2. Run `build_assets.py` locally with a `gh auth token`; diff output.
3. Push; open `github.com/TrebaDripat` in light and dark; run the workflow
   manually once and confirm a bot commit lands (or "no changes").

## Out of scope

- Visitor-driven interaction (issue-based games).
- Making any private repo public.
- Custom domain / external hosting.
