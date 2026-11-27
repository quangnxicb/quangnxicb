#!/usr/bin/env python3
"""Draw the README "Coding Activity" ASCII graph from GitHub contributions (stdlib only).

Cumulative contributions (commits, PRs, reviews, issues; private ones too when the token can see them)
over the last 7 days, one column per ~1.7 h, written between the ascii_graph markers of README.md.
ponytail: GitHub only gives per-day counts, so the line steps at day starts; switch the source to WakaTime
(hourly) if real coding hours are wanted.
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.request

USER = os.environ.get("GH_USER", "quangnxicb")
TOKEN = os.environ.get("GH_STATS_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
WIDTH, HEIGHT, HOURS = 100, 12, 168
README = os.environ.get("README", "README.md")
START, END = "<!-- START_SECTION:ascii_graph -->", "<!-- END_SECTION:ascii_graph -->"

QUERY = """query($u:String!,$f:DateTime!,$t:DateTime!){user(login:$u){contributionsCollection(from:$f,to:$t){
 totalCommitContributions totalPullRequestContributions totalPullRequestReviewContributions totalIssueContributions
 restrictedContributionsCount totalRepositoriesWithContributedCommits
 contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
STATS_SVG = os.environ.get("STATS_SVG", "img/stats.svg")


def write_stats(cc):
    """Own stats card: the public card services only see public repos; the calendar here counts private ones too."""
    rows = [("Tổng đóng góp (1 năm)", cc["contributionCalendar"]["totalContributions"]),
            ("Commit", cc["totalCommitContributions"]),
            ("Pull request", cc["totalPullRequestContributions"]),
            ("Review", cc["totalPullRequestReviewContributions"]),
            ("Repo đã commit", cc["totalRepositoriesWithContributedCommits"])]
    if cc["restrictedContributionsCount"]:  # only when the token cannot see the private repos themselves
        rows.insert(1, ("Đóng góp ở repo riêng tư", cc["restrictedContributionsCount"]))
    h = 60 + 26 * len(rows)
    body = "".join(f'<text class="l" x="25" y="{62 + 26 * i}">{k}</text><text class="v" x="390" y="{62 + 26 * i}" '
                   f'text-anchor="end">{v:,}</text>' for i, (k, v) in enumerate(rows))
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="420" height="{h}" viewBox="0 0 420 {h}">'
           '<style>text{font:600 14px "Segoe UI",Ubuntu,Sans-Serif}.t{font-size:18px;fill:#2f80ed}.l{fill:#434d58}'
           '.v{fill:#333}@media (prefers-color-scheme:dark){.l{fill:#9fa8b3}.v{fill:#e6edf3}.t{fill:#58a6ff}}</style>'
           f'<text class="t" x="25" y="32">Thống kê GitHub của Quang</text>{body}</svg>')
    os.makedirs(os.path.dirname(STATS_SVG) or ".", exist_ok=True)
    open(STATS_SVG, "w", encoding="utf-8").write(svg)


def fetch_days(now):
    body = json.dumps({"query": QUERY, "variables": {
        "u": USER, "f": (now - dt.timedelta(days=365)).isoformat(), "t": now.isoformat()}}).encode()
    req = urllib.request.Request("https://api.github.com/graphql", body, {
        "Authorization": f"bearer {TOKEN}", "Content-Type": "application/json", "User-Agent": "profile-activity"})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    if "errors" in data:
        sys.exit(f"GraphQL error: {data['errors']}")
    cc = data["data"]["user"]["contributionsCollection"]
    write_stats(cc)
    weeks = cc["contributionCalendar"]["weeks"]
    return {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}


def series(days, now):
    """Cumulative count sampled every HOURS/WIDTH hours across the last 7 days."""
    start = now - dt.timedelta(hours=HOURS)
    base = sum(c for d, c in days.items() if d < start.date().isoformat())
    out = []
    for i in range(WIDTH):
        t = start + dt.timedelta(hours=HOURS * (i + 1) / WIDTH)
        out.append(base + sum(c for d, c in days.items() if start.date().isoformat() <= d <= t.date().isoformat()))
    return out


def plot(values, height=HEIGHT):
    """Minimal port of github.com/guptarohit/asciigraph Plot (same glyphs as the MacroPower profile)."""
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1
    rows = [round((v - lo) / span * (height - 1)) for v in values]
    labels = [f"{lo + span * r / (height - 1):,.0f} đóng góp" for r in range(height)]
    lw = max(len(s) for s in labels)
    grid = [[" "] * (len(values) + 1) for _ in range(height)]
    for r in range(height):
        grid[r][0] = "┤"
    grid[rows[0]][0] = "┼"
    for x in range(len(values) - 1):
        y0, y1 = rows[x], rows[x + 1]
        if y0 == y1:
            grid[y0][x + 1] = "─"
            continue
        grid[y1][x + 1] = "╰" if y0 > y1 else "╭"
        grid[y0][x + 1] = "╮" if y0 > y1 else "╯"
        for y in range(min(y0, y1) + 1, max(y0, y1)):
            grid[y][x + 1] = "│"
    grid[rows[-1]][len(values)] = "─"
    lines = [f"{labels[r]:>{lw}} {''.join(grid[r])}" for r in range(height - 1, -1, -1)]
    pad = " " * (lw + 1)
    step = len(values) // 7
    axis = pad + "┼" + "".join(("┬" if (i + 1) % step == 0 else "─") for i in range(len(values) - 1)) + "┤"
    ticks = [f"-{7 - k}d" for k in range(7)] + ["now"]
    lab = list(" " * (len(axis) + 4))
    for k, t in enumerate(ticks):
        pos = lw + 1 + k * step - len(t) // 2
        lab[pos:pos + len(t)] = t
    return "\n".join(lines + [axis, "".join(lab).rstrip()])


def main():
    now = dt.datetime.now(dt.timezone.utc)
    graph = plot(series(fetch_days(now), now))
    stamp = now.astimezone(dt.timezone(dt.timedelta(hours=7))).strftime("%d/%m/%Y %H:%M (GMT+7)")
    block = f"{START}\n\n```\n{graph}\n```\n\n<sub>Cập nhật {stamp}</sub>\n\n{END}"
    text = open(README, encoding="utf-8").read()
    new = re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: block, text, flags=re.S)
    if new == text and START not in text:
        sys.exit("markers not found in README")
    open(README, "w", encoding="utf-8").write(new)


if __name__ == "__main__":
    main()
