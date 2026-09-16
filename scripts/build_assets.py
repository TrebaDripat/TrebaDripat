"""Build the profile SVG screens.

    python scripts/build_assets.py            # data screens (needs GITHUB_TOKEN)
    python scripts/build_assets.py --static   # also rebuild the hand-designed screens
    python scripts/build_assets.py --offline  # use sample data, no network

Static screens: title, dialogue, inventory.  Data screens: charsheet, worldmap.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import gb

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CONFIG = json.loads((Path(__file__).parent / "profile_config.json").read_text(encoding="utf-8"))

GRAPHQL = "https://api.github.com/graphql"


# ----------------------------------------------------------------- data ----

def gql(query: str, variables: dict, token: str) -> dict:
    req = urllib.request.Request(
        GRAPHQL,
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(f"GraphQL errors: {payload['errors']}")
    return payload["data"]


USER_Q = """
query($login:String!){
  user(login:$login){
    createdAt followers{totalCount}
    repositories(ownerAffiliations:OWNER,first:100,isFork:false){
      totalCount
      nodes{ name defaultBranchRef{ name target{ ... on Commit{ history{ totalCount } } } } }
    }
  }
}"""

CAL_Q = """
query($login:String!,$from:DateTime!,$to:DateTime!){
  user(login:$login){
    contributionsCollection(from:$from,to:$to){
      contributionCalendar{ weeks{ contributionDays{ date contributionCount } } }
    }
  }
}"""

HIST_Q = """
query($login:String!,$name:String!,$since:GitTimestamp!,$after:String){
  repository(owner:$login,name:$name){
    defaultBranchRef{ target{ ... on Commit{
      history(since:$since,first:100,after:$after){
        pageInfo{ hasNextPage endCursor }
        nodes{ committedDate }
      } } } }
  }
}"""


def fetch(login: str, token: str) -> dict:
    """Profile numbers.

    Commit XP counts every commit on the default branch of repos this user
    owns (public and private), because commits authored under a different
    e-mail do not show up in GitHub's own contribution graph.  The world map
    merges those commit dates with the official contribution calendar.
    """
    u = gql(USER_Q, {"login": login}, token)["user"]
    created = datetime.fromisoformat(u["createdAt"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    since = datetime.fromtimestamp(now.timestamp() - 371 * 86400, tz=timezone.utc)

    total_commits = 0
    per_day: dict[str, int] = {}
    for repo in u["repositories"]["nodes"]:
        ref = repo["defaultBranchRef"]
        if not ref:
            continue
        total_commits += ref["target"]["history"]["totalCount"]
        after = None
        while True:
            h = gql(HIST_Q, {"login": login, "name": repo["name"], "since": since.isoformat(), "after": after}, token)
            h = h["repository"]["defaultBranchRef"]["target"]["history"]
            for n in h["nodes"]:
                day = n["committedDate"][:10]
                per_day[day] = per_day.get(day, 0) + 1
            if not h["pageInfo"]["hasNextPage"]:
                break
            after = h["pageInfo"]["endCursor"]

    cal = gql(CAL_Q, {"login": login, "from": since.isoformat(), "to": now.isoformat()}, token)
    weeks = cal["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    calendar = [
        [{"date": d["date"], "contributionCount": max(d["contributionCount"], per_day.get(d["date"], 0))} for d in w["contributionDays"]]
        for w in weeks
    ]

    return {
        "created": created.date().isoformat(),
        "followers": u["followers"]["totalCount"],
        "repos": u["repositories"]["totalCount"],
        "total_commits": total_commits,
        "calendar": calendar,
    }


def sample_data() -> dict:
    import random

    rnd = random.Random(7)
    today = date.today().toordinal()
    weeks = []
    for w in range(53):
        days = []
        for d in range(7):
            o = today - (52 - w) * 7 - (6 - d)
            days.append({"date": date.fromordinal(o).isoformat(), "contributionCount": max(0, int(rnd.gauss(2, 3)))})
        weeks.append(days)
    return {"created": "2020-04-06", "followers": 4, "repos": 15, "total_commits": 1840, "calendar": weeks}


# ------------------------------------------------------------ formulas ----

def level(commits: int) -> tuple[int, float]:
    lvl = max(1, int(math.sqrt(commits / 10)))
    lo, hi = 10 * lvl**2, 10 * (lvl + 1) ** 2
    return lvl, (commits - lo) / (hi - lo)


def playtime(created_iso: str) -> str:
    c = date.fromisoformat(created_iso)
    t = date.today()
    months = (t.year - c.year) * 12 + (t.month - c.month)
    return f"{months // 12}Y {months % 12}M"


# ------------------------------------------------------------- screens ----

def title_screen() -> str:
    W = gb.WIDTH
    css = gb.HERO_CSS + """
.blink{animation:blink 1.2s steps(1) infinite}
@keyframes blink{0%,70%{opacity:1}70.01%,100%{opacity:0}}
.wave{animation:wave 1.6s steps(1) infinite}
@keyframes wave{0%,50%{transform:translateY(0)}50.01%,100%{transform:translateY(4px)}}
.cloud{animation:drift 14s linear infinite}
@keyframes drift{from{transform:translateX(0)}to{transform:translateX(-760px)}}
"""
    b = []
    # sky stripes
    for i in range(3):
        b.append(gb.rect(16, 16 + i * 8, W - 32, 4, gb.C2))
    # clouds (looping strip: two copies)
    cloud = ["..####....", ".######...", "##########", "##########"]
    for dx in (0, 760):
        for cx in (60, 300, 520):
            b.append(gb.pixels(cx + dx, 40, cloud, 4, {"#": gb.C2}, extra='class="cloud"'))
    # ground
    b.append(gb.rect(16, 232, W - 32, 8, gb.C1))
    b.append(gb.rect(16, 240, W - 32, 32, gb.C0))
    for gx in range(24, W - 24, 32):
        b.append(gb.rect(gx, 224, 8, 8, gb.C1))
    # logo
    b.append(gb.text(W // 2, 120, "TREBADRIPAT", 40, extra='text-anchor="middle"'))
    b.append(gb.text(W // 2, 156, "a nikos3rd adventure", 14, gb.C1, extra='text-anchor="middle"'))
    # flag and hero
    b.append(gb.pixels(W // 2 - 24 - 120, 176, gb.FLAG, 4, extra='class="wave"'))
    b.append(gb.hero(W // 2 + 96, 176))
    # press start
    b.append(gb.text(W // 2, 214, "PRESS START", 16, extra='text-anchor="middle" class="blink"'))
    b.append(gb.text(W - 32, 262, "(c)2020-%d" % date.today().year, 10, gb.C3, extra='text-anchor="end"'))
    return gb.svg(288, "".join(b), css, "Title screen")


def dialogue_screen() -> str:
    lines = CONFIG["dialogue"]
    W = gb.WIDTH
    per = 4.5  # seconds per line
    total = per * len(lines)
    css = gb.HERO_CSS + """
.cur{animation:blink .6s steps(1) infinite}
@keyframes blink{0%,50%{opacity:1}50.01%,100%{opacity:0}}
"""
    b = [gb.frame(24, 24, W - 48, 128)]
    b.append(gb.hero(48, 48, 5))
    for i, line in enumerate(lines):
        n = len(line)
        start = i * per
        # typing: clip-path width grows in n steps, then line is hidden when next starts
        css += f"""
.l{i}{{animation:show{i} {total}s steps(1) infinite}}
@keyframes show{i}{{0%{{opacity:0}}{start/total*100:.2f}%{{opacity:1}}{(start+per)/total*100:.2f}%{{opacity:0}}100%{{opacity:0}}}}
.t{i}{{animation:type{i} {total}s steps({n}) infinite}}
@keyframes type{i}{{0%{{width:0}}{start/total*100:.2f}%{{width:0}}{(start+per*0.6)/total*100:.2f}%{{width:600px}}100%{{width:600px}}}}
"""
        b.append(
            f'<g class="l{i}"><clipPath id="c{i}"><rect class="t{i}" x="128" y="40" width="0" height="96"/></clipPath>'
            f'<g clip-path="url(#c{i})">{wrap_text(128, 72, line, 14, 34)}</g></g>'
        )
    b.append(gb.text(W - 48, 140, "▼", 12, extra='text-anchor="end" class="cur"'))
    b.append(gb.text(W // 2, 176, "* NPC: NIKOS *", 12, gb.C1, extra='text-anchor="middle"'))
    return gb.svg(192, "".join(b), css, "Dialogue")


def wrap_text(x: int, y: int, s: str, size: int, cols: int) -> str:
    words, lines, cur = s.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > cols:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    lines.append(cur)
    return "".join(gb.text(x, y + i * 24, ln, size) for i, ln in enumerate(lines))


def inventory_screen() -> str:
    items = CONFIG["inventory"]
    W = gb.WIDTH
    cols = 8
    cell = 88
    x0 = (W - cols * cell) // 2 + 4
    css = """
.sel{animation:sel 0.8s steps(1) infinite}
@keyframes sel{0%,50%{opacity:1}50.01%,100%{opacity:0}}
"""
    b = [gb.text(W // 2, 48, "- INVENTORY -", 18, extra='text-anchor="middle"')]
    for i, (abbr, name) in enumerate(items):
        cx = x0 + (i % cols) * cell
        cy = 72 + (i // cols) * 96
        b.append(gb.rect(cx, cy, 80, 56, gb.C0))
        b.append(gb.rect(cx + 4, cy + 4, 72, 48, gb.C2))
        b.append(gb.text(cx + 40, cy + 34, abbr, 16, extra='text-anchor="middle"'))
        b.append(gb.text(cx + 40, cy + 72, name, 8, extra='text-anchor="middle"'))
    # selection cursor on first item
    b.append(
        f'<g class="sel">{gb.rect(x0 - 4, 68, 88, 64, gb.C0)}{gb.rect(x0, 72, 80, 56, gb.C2)}'
        f'{gb.text(x0 + 40, 106, items[0][0], 16, extra="text-anchor=\'middle\'")}</g>'
    )
    rows = math.ceil(len(items) / cols)
    h = 72 + rows * 96 + 24
    b.append(gb.text(W - 32, h - 28, f"{len(items)}/{cols*rows} SLOTS", 10, gb.C1, extra='text-anchor="end"'))
    return gb.svg(h, "".join(b), css, "Inventory")


def charsheet_screen(d: dict) -> str:
    W = gb.WIDTH
    lvl, xp = level(d["total_commits"])
    css = gb.HERO_CSS + """
.grow{transform-origin:left;animation:grow 1.6s steps(12) 1 both}
@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
"""
    b = [gb.frame(24, 24, W - 48, 320)]
    b.append(gb.hero(56, 60, 6))
    b.append(gb.text(160, 68, CONFIG["hero_name"], 20))
    b.append(gb.text(160, 92, CONFIG["class"], 10, gb.C1))
    b.append(gb.text(160, 112, f"LV {lvl:>3}", 16))
    b.append(gb.text(320, 112, f"{d['total_commits']} COMMITS", 10, gb.C1))
    b.append(gb.text(W - 56, 68, CONFIG["location"], 10, gb.C1, extra='text-anchor="end"'))
    b.append(gb.text(W - 56, 88, "PLAYTIME " + playtime(d["created"]), 10, gb.C1, extra='text-anchor="end"'))

    hp = min(1.0, d["repos"] / 40)
    mp = min(1.0, d["followers"] / 100)
    b.append(gb.bar(160, 128, 320, hp, "HP", "grow"))
    b.append(gb.text(600, 142, f"{d['repos']} REPOS", 10, gb.C1))
    b.append(gb.bar(160, 156, 320, mp, "MP", "grow"))
    b.append(gb.text(600, 170, f"{d['followers']} ALLIES", 10, gb.C1))
    b.append(gb.bar(160, 184, 320, xp, "XP", "grow"))
    b.append(gb.text(600, 198, f"NEXT LV {int((1-xp)*(10*(lvl+1)**2-10*lvl**2))}", 10, gb.C1))

    # stats grid
    y = 236
    for i, (name, val) in enumerate(CONFIG["stats"].items()):
        col, row = i % 2, i // 2
        x = 56 + col * 360
        yy = y + row * 32
        b.append(gb.text(x, yy + 14, name, 10))
        b.append(gb.rect(x + 120, yy, 200, 16, gb.C0))
        b.append(gb.rect(x + 124, yy + 4, 192, 8, gb.C2))
        b.append(gb.rect(x + 124, yy + 4, int(192 * val / 10 / 4) * 4, 8, gb.C0, cls="k grow"))
        b.append(gb.text(x + 336, yy + 13, f"{val:>2}", 10))

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    b.append(gb.text(W // 2, 368, f"SAVED {stamp}", 10, gb.C1, extra='text-anchor="middle"'))
    return gb.svg(384, "".join(b), css, "Character sheet")


TILES = {
    0: ["....", "....", "....", "...."],           # plain
    1: ["....", ".#..", "...#", "...."],           # grass
    2: [".##.", "####", ".##.", ".#.."],           # tree
    3: ["..#.", ".###", "####", "...."],           # hill
    4: ["..#.", ".###", "#####"[:4], "####"],      # mountain
}


def tier(c: int) -> int:
    return 0 if c == 0 else 1 if c <= 2 else 2 if c <= 5 else 3 if c <= 9 else 4


def worldmap_screen(d: dict) -> str:
    weeks = d["calendar"]
    cell = 12
    x0, y0 = 40, 56
    W = gb.WIDTH
    css = gb.HERO_CSS
    b = [gb.text(W // 2, 40, "- WORLD MAP -  LAST 53 WEEKS", 14, extra='text-anchor="middle"')]
    last = None
    for wi, week in enumerate(weeks[-53:]):
        for di, day in enumerate(week):
            x, y = x0 + wi * cell, y0 + di * cell
            t = tier(day["contributionCount"])
            base = gb.C3 if t == 0 else gb.C2
            b.append(gb.rect(x, y, cell, cell, base))
            if t:
                b.append(gb.pixels(x + 2, y + 2, TILES[t], 2, {"#": gb.C0 if t >= 3 else gb.C1}))
            last = (x, y)
    # water border
    b.append(gb.rect(x0 - 8, y0 - 8, 53 * cell + 16, 4, gb.C1))
    b.append(gb.rect(x0 - 8, y0 + 7 * cell + 4, 53 * cell + 16, 4, gb.C1))
    if last:
        b.append(gb.hero(last[0] - 2, last[1] - 12, 1))
        b.append(gb.text(last[0] + 8, last[1] - 14, "YOU", 8))
    # legend
    ly = y0 + 7 * cell + 28
    names = ["PLAIN", "GRASS", "FOREST", "HILLS", "PEAK"]
    for i, n in enumerate(names):
        lx = 40 + i * 140
        b.append(gb.rect(lx, ly, cell, cell, gb.C3 if i == 0 else gb.C2))
        if i:
            b.append(gb.pixels(lx + 2, ly + 2, TILES[i], 2, {"#": gb.C0 if i >= 3 else gb.C1}))
        b.append(gb.text(lx + 20, ly + 11, n, 8))
    total = sum(day["contributionCount"] for w in weeks for day in w)
    b.append(gb.text(W - 40, ly + 40, f"{total} CONTRIBUTIONS EXPLORED", 10, gb.C1, extra='text-anchor="end"'))
    return gb.svg(ly + 60, "".join(b), css, "World map")


# ---------------------------------------------------------------- main ----

def write(name: str, content: str) -> bool:
    p = ASSETS / name
    if p.exists() and p.read_text(encoding="utf-8") == content:
        print(f"  = {name} (unchanged)")
        return False
    p.write_text(content, encoding="utf-8", newline="\n")
    print(f"  + {name} ({len(content)//1024} KB)")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--static", action="store_true", help="also rebuild static screens")
    ap.add_argument("--offline", action="store_true", help="use sample data")
    a = ap.parse_args()
    ASSETS.mkdir(exist_ok=True)

    if a.static:
        write("title.svg", title_screen())
        write("dialogue.svg", dialogue_screen())
        write("inventory.svg", inventory_screen())

    if a.offline:
        d = sample_data()
    else:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            print("GITHUB_TOKEN missing (or pass --offline)", file=sys.stderr)
            return 2
        d = fetch(CONFIG["login"], token)
    print(f"data: commits={d['total_commits']} repos={d['repos']} followers={d['followers']}")
    write("charsheet.svg", charsheet_screen(d))
    write("worldmap.svg", worldmap_screen(d))
    return 0


if __name__ == "__main__":
    sys.exit(main())
