#!/usr/bin/env python3
"""Generate a stock-market-style GitHub profile dashboard from real GitHub data.

The chart is a visualization of GitHub contributions, not a financial asset.
Only Python's standard library is required.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import pathlib
import sys
import urllib.request
from collections import Counter

USERNAME = os.environ.get("GITHUB_USERNAME", "Ramdani101")
TOKEN = os.environ.get("GITHUB_TOKEN")
OUTPUT = pathlib.Path("assets/stock-dashboard.svg")

QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    login
    name
    url
    avatarUrl
    followers { totalCount }
    repositories(
      first: 100
      privacy: PUBLIC
      ownerAffiliations: OWNER
      orderBy: { field: UPDATED_AT, direction: DESC }
    ) {
      totalCount
      nodes {
        name
        url
        description
        isFork
        isArchived
        updatedAt
        stargazerCount
        forkCount
        primaryLanguage { name color }
      }
    }
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""


def esc(value: object) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def fetch_profile() -> dict:
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN is required to query the GitHub GraphQL API.")

    now = dt.datetime.now(dt.timezone.utc)
    start = now - dt.timedelta(days=365)
    variables = {
        "login": USERNAME,
        "from": start.replace(hour=0, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z"),
        "to": now.isoformat().replace("+00:00", "Z"),
    }
    payload = json.dumps({"query": QUERY, "variables": variables}).encode("utf-8")
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "github-stock-profile-dashboard",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        result = json.loads(response.read().decode("utf-8"))

    if result.get("errors"):
        messages = "; ".join(error.get("message", "Unknown GraphQL error") for error in result["errors"])
        raise RuntimeError(f"GitHub GraphQL request failed: {messages}")
    user = result.get("data", {}).get("user")
    if not user:
        raise RuntimeError(f"GitHub user @{USERNAME} was not found or is not visible.")
    return user


def text(x, y, value, size=14, color="#c9d1d9", weight=400, anchor="start", family="Inter, Segoe UI, Arial, sans-serif", extra=""):
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="{anchor}" '
        f'font-family="{family}" {extra}>{esc(value)}</text>'
    )


def rounded_rect(x, y, width, height, fill, stroke="#27313b", radius=12):
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
    )


def compact(value: int) -> str:
    return f"{value:,}"


def make_dashboard(user: dict) -> str:
    now = dt.datetime.now(dt.timezone.utc).date()
    repos_data = user.get("repositories", {})
    all_repos = repos_data.get("nodes", [])
    public_repo_count = repos_data.get("totalCount", len(all_repos))

    owned_repos = [
        repo for repo in all_repos
        if not repo.get("isFork")
        and not repo.get("isArchived")
        and repo.get("name", "").lower() != USERNAME.lower()
    ]
    owned_repos.sort(key=lambda repo: repo.get("updatedAt", ""), reverse=True)

    # Keep the profile's most recognizable projects in the portfolio, then
    # fill any missing slots with recently updated non-fork repositories.
    holding_order = [
        "bigdata-streaming",
        "dukasaha",
        "midterm-project",
        "codeforces-solution",
        "mancing-perkoro-simulator",
        "sosial-gabut-media",
    ]
    owned_by_name = {repo.get("name", "").lower(): repo for repo in owned_repos}
    holdings = [owned_by_name[name] for name in holding_order if name in owned_by_name]
    holdings.extend(repo for repo in owned_repos if repo not in holdings)
    holdings = holdings[:6]

    # Watchlist includes selected public projects, including a fork if it is
    # part of the profile's public project activity.
    ticker_order = [
        "candy-crush-lokal",
        "dukasaha",
        "monitoring-ekonomi-lamongan",
        "bigdata-streaming",
    ]
    all_by_name = {repo.get("name", "").lower(): repo for repo in all_repos}
    ticker_repos = [all_by_name[name] for name in ticker_order if name in all_by_name]
    ticker_repos.extend(repo for repo in owned_repos if repo not in ticker_repos)
    ticker_repos = ticker_repos[:4]

    stars = sum(int(repo.get("stargazerCount") or 0) for repo in all_repos)
    followers = int(user.get("followers", {}).get("totalCount", 0))
    language_counts = Counter(
        language.get("name")
        for language in (repo.get("primaryLanguage") or {} for repo in owned_repos)
        if language.get("name")
    )
    sector = language_counts.most_common(1)[0][0] if language_counts else "SOFTWARE"

    calendar = (
        user.get("contributionsCollection", {})
        .get("contributionCalendar", {})
    )
    all_weeks = calendar.get("weeks", [])
    all_days = [
        day
        for week in all_weeks
        for day in week.get("contributionDays", [])
    ]
    all_days.sort(key=lambda day: day.get("date", ""))

    day_dates = []
    day_counts = []
    for day in all_days:
        try:
            day_dates.append(dt.date.fromisoformat(day["date"]))
            day_counts.append(int(day.get("contributionCount", 0)))
        except (KeyError, TypeError, ValueError):
            continue

    by_date = dict(zip(day_dates, day_counts))
    last_30 = sum(count for date, count in by_date.items() if (now - date).days < 30)
    previous_30 = sum(
        count for date, count in by_date.items()
        if 30 <= (now - date).days < 60
    )
    if previous_30:
        change = (last_30 - previous_30) / previous_30 * 100
        change_label = f"{change:+.1f}% VS PRIOR 30D"
        change_color = "#3fb950" if change >= 0 else "#ff5b5b"
        change_arrow = "▲" if change >= 0 else "▼"
    elif last_30:
        change_label = "NEW ACTIVITY VS PRIOR 30D"
        change_color = "#3fb950"
        change_arrow = "▲"
    else:
        change_label = "NO CHANGE VS PRIOR 30D"
        change_color = "#8b949e"
        change_arrow = "•"

    # Build a rolling 7-day contribution index, then draw true OHLC-style
    # weekly candles from the daily index values. Weekly volume is the sum
    # of that week's contribution counts.
    rolling = []
    for index in range(len(day_counts)):
        rolling.append(sum(day_counts[max(0, index - 6): index + 1]))
    rolling_by_date = dict(zip(day_dates, rolling))
    weekly = []
    for week in all_weeks[-26:]:
        days = week.get("contributionDays", [])
        if not days:
            continue
        values = []
        volume = 0
        for day in days:
            try:
                day_date = dt.date.fromisoformat(day["date"])
            except (KeyError, ValueError):
                continue
            values.append(rolling_by_date.get(day_date, 0))
            volume += int(day.get("contributionCount", 0))
        if values:
            weekly.append({
                "date": days[0].get("date", ""),
                "open": values[0],
                "close": values[-1],
                "high": max(values),
                "low": min(values),
                "volume": volume,
            })

    width, height = 960, 1130
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="GitHub contribution stock dashboard for {esc(USERNAME)}">',
        '<title>GitHub Contribution Index — Ramdani101</title>',
        '<desc>A stock-market-inspired dashboard built from the public GitHub contribution calendar and public repositories. Not a financial asset.</desc>',
        '<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#101820"/><stop offset="100%" stop-color="#0b0f14"/></linearGradient></defs>',
        '<rect width="960" height="1130" fill="url(#bg)"/>',
        '<rect x="8" y="8" width="944" height="1114" rx="18" fill="none" stroke="#252d36" stroke-width="1.5"/>',
    ]

    # Header / ticker identity.
    out += [
        '<circle cx="78" cy="72" r="27" fill="#12261b" stroke="#3fb950" stroke-width="3"/>',
        text(78, 80, "RM", 17, "#3fb950", 800, "middle", "ui-monospace, SFMono-Regular, Consolas, monospace"),
        text(120, 68, "$RAMDA", 29, "#f0f6fc", 800),
        '<rect x="270" y="43" width="145" height="28" rx="14" fill="#281a28" stroke="#f04f73"/>',
        text(342, 62, f"SECTOR · {sector.upper()[:14]}", 10, "#ff6687", 700, "middle", "ui-monospace, SFMono-Regular, Consolas, monospace", 'letter-spacing="1"'),
        text(120, 96, f"{user.get('name') or USERNAME} · GitHub · contribution index", 13, "#9da7b3"),
        text(900, 73, compact(last_30), 39, "#f0f6fc", 800, "end"),
        text(900, 98, "CONTRIBUTIONS / LAST 30 DAYS", 10, "#9da7b3", 600, "end", "ui-monospace, SFMono-Regular, Consolas, monospace", 'letter-spacing="0.7"'),
        text(900, 120, f"{change_arrow}  {change_label}", 11, change_color, 600, "end", "ui-monospace, SFMono-Regular, Consolas, monospace"),
    ]

    # Main chart panel.
    out += [rounded_rect(30, 145, 900, 440, "#0e141b", "#27313b", 12)]
    out += [
        text(58, 181, "CONTRIBUTION INDEX", 12, "#e6edf3", 700, extra='letter-spacing="1.2"'),
        text(900, 181, "7D ROLLING · WEEKLY CANDLES", 10, "#8b949e", 500, "end", "ui-monospace, SFMono-Regular, Consolas, monospace"),
    ]

    chart_left, chart_right = 84, 905
    chart_top, chart_bottom = 220, 425
    chart_height = chart_bottom - chart_top
    max_value = max([item["high"] for item in weekly] or [1])
    max_value = max(max_value, 1)
    grid_values = [max_value, max_value * 0.75, max_value * 0.5, max_value * 0.25, 0]
    for value in grid_values:
        y = chart_bottom - (value / max_value) * chart_height
        out.append(f'<line x1="{chart_left}" y1="{y:.1f}" x2="{chart_right}" y2="{y:.1f}" stroke="#26313b" stroke-width="1"/>')
        out.append(text(68, y + 4, str(round(value)), 9, "#687582", 400, "end", "ui-monospace, SFMono-Regular, Consolas, monospace"))

    if weekly:
        slot = (chart_right - chart_left) / len(weekly)
        candle_width = min(16, slot * 0.55)
        max_volume = max([item["volume"] for item in weekly] or [1]) or 1
        for index, item in enumerate(weekly):
            center = chart_left + slot * (index + 0.5)

            def y_for(value):
                return chart_bottom - (value / max_value) * chart_height

            y_high = y_for(item["high"])
            y_low = y_for(item["low"])
            y_open = y_for(item["open"])
            y_close = y_for(item["close"])
            color = "#3fb950" if item["close"] >= item["open"] else "#ff5555"
            body_y = min(y_open, y_close)
            body_h = max(3, abs(y_close - y_open))

            out.append(f'<line x1="{center:.1f}" y1="{y_high:.1f}" x2="{center:.1f}" y2="{y_low:.1f}" stroke="{color}" stroke-width="1.6"/>')
            out.append(f'<rect x="{center - candle_width/2:.1f}" y="{body_y:.1f}" width="{candle_width:.1f}" height="{body_h:.1f}" rx="1" fill="{color}"/>')

            volume_h = max(2, (item["volume"] / max_volume) * 48)
            out.append(f'<rect x="{center - candle_width/2:.1f}" y="{480 - volume_h:.1f}" width="{candle_width:.1f}" height="{volume_h:.1f}" rx="1" fill="#66717d" opacity="0.62"/>')

            if index == 0 or (item.get("date", "")[5:7] != weekly[index - 1].get("date", "")[5:7]):
                try:
                    month = dt.date.fromisoformat(item["date"]).strftime("%b").upper()
                    out.append(text(center, 502, month, 9, "#768390", 500, "middle", "ui-monospace, SFMono-Regular, Consolas, monospace"))
                except ValueError:
                    pass
    else:
        out.append(text(490, 320, "CONTRIBUTION HISTORY UNAVAILABLE", 13, "#8b949e", 600, "middle"))

    out += [
        text(84, 522, "VOLUME = CONTRIBUTIONS PER WEEK · LAST 26 WEEKS", 9, "#8b949e", 400, "start", "ui-monospace, SFMono-Regular, Consolas, monospace"),
        text(905, 522, "SOURCE: GITHUB", 9, "#687582", 400, "end", "ui-monospace, SFMono-Regular, Consolas, monospace"),
    ]

    # Compact ticker tape of current projects.
    out.append('<rect x="58" y="540" width="844" height="35" rx="4" fill="#151d26"/>')
    ticker_slots = [75, 284, 493, 702]
    for index, x in enumerate(ticker_slots):
        if index >= len(ticker_repos):
            continue
        repo = ticker_repos[index]
        language = repo.get("primaryLanguage") or {}
        badge_color = language.get("color") or "#64748b"
        language_short = (language.get("name") or "GH")[:2].upper()
        repo_name = repo.get("name", "project")
        star_count = int(repo.get("stargazerCount") or 0)
        active = repo_is_active(repo, now)
        arrow_color = "#3fb950" if active else "#8b949e"
        arrow = "▲" if active else "•"
        out.append(f'<rect x="{x}" y="549" width="17" height="17" rx="4" fill="{esc(badge_color)}"/>')
        out.append(text(x + 8.5, 561, language_short, 8, "#ffffff", 800, "middle", "ui-monospace, SFMono-Regular, Consolas, monospace"))
        out.append(f'<a xlink:href="{esc(repo.get("url", "#"))}">')
        out.append(text(x + 25, 562, repo_name[:17].upper(), 10, "#f0f6fc", 500))
        out.append("</a>")
        out.append(text(x + 156, 562, f"★ {star_count}", 9, "#c9d1d9", 600))
        out.append(text(x + 190, 562, arrow, 10, arrow_color, 700))

    # Company profile card — intentionally no long bio.
    out += [
        rounded_rect(30, 605, 900, 150, "#0e131a", "#27313b", 13),
        text(60, 637, "▲  COMPANY PROFILE", 10, "#3fb950", 700, extra='letter-spacing="1.3" font-family="ui-monospace, SFMono-Regular, Consolas, monospace"'),
        '<line x1="30" y1="652" x2="930" y2="652" stroke="#27313b"/>',
        text(65, 695, user.get("name") or USERNAME, 27, "#f0f6fc", 800),
        text(65, 723, f"@{USERNAME}  ·  GitHub", 13, "#c9d1d9", 400),
        text(65, 741, f"{compact(followers)} followers   ·   {compact(public_repo_count)} public repositories   ·   ★ {compact(stars)} stars", 11, "#8b949e", 500, "start", "ui-monospace, SFMono-Regular, Consolas, monospace"),
        '<circle cx="835" cy="699" r="51" fill="#11241a" stroke="#3fb950" stroke-width="4"/>',
        text(835, 710, "RM", 29, "#3fb950", 800, "middle", "ui-monospace, SFMono-Regular, Consolas, monospace"),
    ]

    # Holdings table.
    out += [
        rounded_rect(30, 775, 900, 305, "#0e131a", "#27313b", 13),
        text(60, 808, "▲  HOLDINGS", 10, "#3fb950", 700, extra='letter-spacing="1.3" font-family="ui-monospace, SFMono-Regular, Consolas, monospace"'),
        '<line x1="30" y1="824" x2="930" y2="824" stroke="#27313b"/>',
    ]

    if not holdings:
        out.append(text(65, 872, "No public repositories found.", 13, "#8b949e"))
    else:
        for index, repo in enumerate(holdings):
            y = 857 + index * 34
            language = repo.get("primaryLanguage") or {}
            language_name = language.get("name") or "—"
            language_color = language.get("color") or "#64748b"
            repo_name = repo.get("name", "project")
            symbol = "".join(part[0] for part in repo_name.replace("_", "-").split("-") if part)[:5].upper() or "GH"
            fork_count = int(repo.get("forkCount") or 0)
            star_count = int(repo.get("stargazerCount") or 0)
            active = repo_is_active(repo, now)
            status = "▲ ACTIVE" if active else "▼ QUIET"
            status_color = "#3fb950" if active else "#ff5555"

            if index:
                out.append(f'<line x1="62" y1="{y - 20}" x2="898" y2="{y - 20}" stroke="#303943" stroke-width="1"/>')
            out.append(text(64, y, symbol, 11, "#dce3ea", 700, "start", "ui-monospace, SFMono-Regular, Consolas, monospace"))
            out.append(f'<rect x="152" y="{y - 13}" width="17" height="17" rx="4" fill="{esc(language_color)}"/>')
            out.append(text(160.5, y - 1, (language_name[:2] if language_name != "—" else "GH").upper(), 7, "#ffffff", 800, "middle", "ui-monospace, SFMono-Regular, Consolas, monospace"))
            out.append(f'<a xlink:href="{esc(repo.get("url", "#"))}">')
            out.append(text(178, y, repo_name[:42], 12, "#9da7b3", 400))
            out.append("</a>")
            out.append(text(660, y, f"forks {fork_count}", 10, "#8b949e", 400, "start", "ui-monospace, SFMono-Regular, Consolas, monospace"))
            out.append(text(770, y, f"★ {star_count}", 11, "#c9d1d9", 600, "start", "ui-monospace, SFMono-Regular, Consolas, monospace"))
            out.append(text(895, y, status, 10, status_color, 700, "end", "ui-monospace, SFMono-Regular, Consolas, monospace"))

    out += [
        text(480, 1107, "CONTRIBUTION INDEX ONLY  ·  NOT A FINANCIAL ASSET", 9, "#687582", 500, "middle", "ui-monospace, SFMono-Regular, Consolas, monospace", 'letter-spacing="0.8"'),
        "</svg>",
    ]
    return "\n".join(out)


def repo_is_active(repo: dict, today: dt.date) -> bool:
    updated = repo.get("updatedAt")
    if not updated:
        return False
    try:
        updated_date = dt.datetime.fromisoformat(updated.replace("Z", "+00:00")).date()
        return (today - updated_date).days <= 30
    except ValueError:
        return False


def main() -> int:
    try:
        user = fetch_profile()
        svg = make_dashboard(user)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(svg, encoding="utf-8")
        print(f"Updated {OUTPUT} for @{USERNAME}")
        return 0
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
