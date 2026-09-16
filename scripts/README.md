# Profile screen generator

```
python scripts/build_assets.py --static --offline   # everything, sample data
GITHUB_TOKEN=$(gh auth token) python scripts/build_assets.py   # real data
```

- `gb.py` — palette, embedded font, pixel/sprite/frame primitives.
- `build_assets.py` — the five screens. `title`, `dialogue`, `inventory` are
  static (`--static`); `charsheet` and `worldmap` are rebuilt by the workflow.
- `profile_config.json` — text, self-assessed stats, inventory items.
- `fonts/PressStart2P.subset.woff2` — ASCII subset of Press Start 2P (OFL,
  see `fonts/OFL.txt`). Regenerate with
  `python -m fontTools.subset PressStart2P.ttf --unicodes="U+0020-007E,U+25B6,U+25BC" --flavor=woff2`.

## Token

Commit XP and the world map read the default branch of **every repo the
profile owns, private included**. The workflow's built-in `GITHUB_TOKEN`
only sees this one repo, so add a repository secret `PROFILE_TOKEN`
(fine-grained PAT, *All repositories*, permission *Contents: read* and
*Metadata: read*). Without it the workflow still runs but only counts
public repos.
