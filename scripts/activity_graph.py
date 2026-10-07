#!/usr/bin/env python3
"""Generate animated activity graphs (snake, chart, skyline) from GitHub contribution data.

Standard library only. Reads GITHUB_TOKEN (GraphQL) when set, otherwise falls back to the
public contributions page. Writes snake.svg, chart.svg, skyline.svg and current.svg
(one of the three, advancing after a 3-hour publication guard) into the output directory.
"""
import argparse, datetime as dt, html, json, math, os, re, shutil, sys, urllib.request

BG = "#0d1117"
EMPTY = "#161b22"
BLUE = ["#161b22", "#12335a", "#1f5aa6", "#3b82d6", "#58a6ff"]
ORANGE = "#f7786b"
GREY = "#8b949e"
NAMES = ["snake", "chart", "skyline"]
TEXT_CSS = "text{font-family:ui-monospace,Menlo,Consolas,monospace}"


def contribution_caption(days, x, y=22):
    """Describe the exact input window, using the same style for every graph."""
    total = sum(c for _, c in days)
    return ('<text x="%d" y="%d" fill="#58a6ff" font-size="13" font-weight="bold">'
            '%d contributions in the last %d days</text>' % (x, y, total, len(days)))


def fetch(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def days_graphql(user, token):
    q = ("query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{"
         "weeks{contributionDays{date contributionCount}}}}}}")
    body = json.dumps({"query": q, "variables": {"u": user}}).encode()
    out = json.loads(fetch("https://api.github.com/graphql", body, {
        "Authorization": "bearer " + token, "Content-Type": "application/json",
        "User-Agent": "activity-graph"}))
    weeks = out["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return [(d["date"], d["contributionCount"]) for w in weeks for d in w["contributionDays"]]


def days_html(user):
    page = fetch("https://github.com/users/%s/contributions" % user, headers={"User-Agent": "activity-graph"})
    cells = re.findall(r'<td[^>]*data-date="([\d-]+)"[^>]*id="([^"]+)"', page)
    tips = dict(re.findall(r'for="([^"]+)"[^>]*>\s*([^<]*)<', page))
    out = []
    for date, cid in cells:
        m = re.match(r"\s*(\d+) contribution", tips.get(cid, ""))
        out.append((date, int(m.group(1)) if m else 0))
    return out


def get_days(user):
    token = os.environ.get("GITHUB_TOKEN")
    days = []
    if token:
        try:
            days = days_graphql(user, token)
            print("data source: GraphQL")
        except Exception as e:  # fall back to the public page
            print("GraphQL failed (%s), falling back to HTML" % e)
    if not days:
        days = days_html(user)
        print("data source: public contributions page")
    days.sort()
    if len(days) < 300:
        sys.exit("too few days of data: %d" % len(days))
    return days


def grid(days):
    """Return {(week, weekday): (date, count)} with Sunday = row 0."""
    first = dt.date.fromisoformat(days[0][0])
    off = (first.weekday() + 1) % 7  # python Monday=0 -> Sunday=0
    cells = {}
    for i, (d, c) in enumerate(days):
        idx = i + off
        cells[(idx // 7, idx % 7)] = (d, c)
    return cells, (len(days) + off + 6) // 7


def level(c, mx):
    return 0 if c <= 0 else min(4, max(1, math.ceil(4 * c / mx)))


def svg_wrap(w, h, css, body, title):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
            'role="img" aria-label="%s">\n<title>%s</title>\n<style>%s</style>\n'
            '<rect width="100%%" height="100%%" fill="%s"/>\n%s\n</svg>\n'
            % (w, h, w, h, html.escape(title), html.escape(title), css, BG, body))


# ---------------------------------------------------------------- snake
def make_snake(days):
    cells, weeks = grid(days)
    mx = max(c for _, c in days) or 1
    S, G, M, TOP = 12, 2, 16, 44
    step = S + G
    W, H = weeks * step - G + 2 * M, 7 * step - G + M + TOP
    STEP_T, LEN = 0.09, 7
    # head path: enter from above, zigzag columns, leave off the bottom or top
    path = []
    for k in range(LEN + 1, 0, -1):
        path.append((0, -k))
    eat = {}
    for wk in range(weeks):
        rows = range(7) if wk % 2 == 0 else range(6, -1, -1)
        for r in rows:
            eat[(wk, r)] = len(path)
            path.append((wk, r))
    last_wk, last_r = path[-1]
    dr = 1 if last_r == 6 else -1
    for k in range(1, LEN + 2):
        path.append((last_wk, last_r + dr * k))
    P = len(path)
    T = P * STEP_T
    css = [TEXT_CSS, ".c{shape-rendering:geometricPrecision}",
           ".s{animation:mv %.2fs linear infinite}" % T]
    kf = ["@keyframes mv{"]
    for i, (c, r) in enumerate(path):
        kf.append("%.3f%%{transform:translate(%dpx,%dpx)}" % (100.0 * i / (P - 1), M + c * step, TOP + r * step))
    kf.append("}")
    css.append("".join(kf))
    body = []
    for (wk, r), (d, c) in sorted(cells.items()):
        lv = level(c, mx)
        x, y = M + wk * step, TOP + r * step
        if lv == 0:
            body.append('<rect class="c" x="%d" y="%d" width="%d" height="%d" rx="2" fill="%s"/>' % (x, y, S, S, EMPTY))
        else:
            n = "e%d_%d" % (wk, r)
            p = 100.0 * (eat[(wk, r)] + 0.5) / (P - 1)
            css.append("@keyframes %s{0%%,%.3f%%{fill:%s}%.3f%%,100%%{fill:%s}}" % (n, p, BLUE[lv], p + 0.01, EMPTY))
            body.append('<rect class="c" x="%d" y="%d" width="%d" height="%d" rx="2" fill="%s" '
                        'style="animation:%s %.2fs linear infinite"><title>%s: %d</title></rect>'
                        % (x, y, S, S, BLUE[lv], n, T, d, c))
    for i in range(LEN - 1, -1, -1):
        shade = ORANGE if i == 0 else "#e0584a" if i % 2 else "#c9443a"
        size = S if i == 0 else S - 1
        body.append('<rect class="s" x="0" y="0" width="%d" height="%d" rx="3" fill="%s" '
                    'style="animation-delay:-%.2fs"/>' % (size, size, shade, T - i * STEP_T))
    # Keep the snake's off-grid entry/exit behind a clip, away from the caption.
    body = ['<defs><clipPath id="snake-art"><rect x="0" y="32" width="%d" height="%d"/></clipPath></defs>' % (W, H - 32),
            contribution_caption(days, M),
            '<g clip-path="url(#snake-art)">'] + body + ['</g>']
    return svg_wrap(W, H, "".join(css), "\n".join(body), "Contribution snake")


# ---------------------------------------------------------------- chart
def make_chart(days):
    last = days[-31:]
    W, H = 760, 260
    L, R, T, B = 48, 24, 36, 40
    mx = max(c for _, c in last) or 1
    top = max(5, int(math.ceil(mx / 5.0) * 5))
    n = len(last)
    px = lambda i: L + i * (W - L - R) / (n - 1)
    py = lambda c: T + (H - T - B) * (1 - c / float(top))
    pts = [(px(i), py(c)) for i, (_, c) in enumerate(last)]
    line = "M" + " L".join("%.1f %.1f" % p for p in pts)
    area = line + " L%.1f %.1f L%.1f %.1f Z" % (pts[-1][0], H - B, pts[0][0], H - B)
    today = dt.date.fromisoformat(last[-1][0])
    # shade the days in the current month (the latest month shown)
    month = [i for i, (d, _) in enumerate(last) if d[:7] == last[-1][0][:7]]
    shade = ""
    if month:
        x0 = px(month[0]) - 0.5 * (W - L - R) / (n - 1)
        shade = ('<rect x="%.1f" y="%d" width="%.1f" height="%d" fill="%s" opacity="0.07"/>'
                 '<text x="%.1f" y="%d" fill="%s" font-size="11" font-family="monospace">%s</text>'
                 % (x0, T, W - R - x0 + 4, H - B - T, ORANGE, x0 + 6, T + 14, ORANGE,
                    today.strftime("%B").upper()))
    css = (TEXT_CSS +
           ".ln{stroke-dasharray:1;stroke-dashoffset:0;animation:draw 9s ease-in-out infinite}"
           ".ar{opacity:.18;animation:fade 9s ease-in-out infinite}"
           ".pt{opacity:1;animation:pop 9s ease-in-out infinite}"
           "@keyframes draw{0%{stroke-dashoffset:1}45%,92%{stroke-dashoffset:0}100%{stroke-dashoffset:1}}"
           "@keyframes fade{0%,20%{opacity:0}50%,92%{opacity:.18}100%{opacity:0}}"
           "@keyframes pop{0%{opacity:0}2%{opacity:0}6%,92%{opacity:1}100%{opacity:0}}")
    body = [shade]
    for v in range(0, top + 1, top // 5 if top >= 5 else 1):
        y = py(v)
        body.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="#21262d"/>' % (L, W - R, y, y))
        body.append('<text x="%d" y="%.1f" fill="%s" font-size="10" text-anchor="end">%d</text>' % (L - 8, y + 3, GREY, v))
    for i in range(0, n, 5):
        d = dt.date.fromisoformat(last[i][0])
        body.append('<text x="%.1f" y="%d" fill="%s" font-size="10" text-anchor="middle">%s</text>'
                    % (px(i), H - B + 18, GREY, d.strftime("%b %-d")))
    body.append('<path class="ar" d="%s" fill="%s"/>' % (area, GREY))
    body.append('<path class="ln" pathLength="1" d="%s" fill="none" stroke="%s" stroke-width="2.5" '
                'stroke-linejoin="round" stroke-linecap="round"/>' % (line, GREY))
    for i, ((d, c), (x, y)) in enumerate(zip(last, pts)):
        body.append('<circle class="pt" cx="%.1f" cy="%.1f" r="3.4" fill="%s" style="animation-delay:%.2fs">'
                    '<title>%s: %d</title></circle>' % (x, y, ORANGE, 0.08 * i, d, c))
    body.append(contribution_caption(last, L))
    return svg_wrap(W, H, css, "\n".join(body), "Contributions over the last 31 days")


# ---------------------------------------------------------------- skyline
def shade_hex(h, f):
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v * f))) for v in (r, g, b))


def make_skyline(days):
    cells, weeks = grid(days)
    mx = max(c for _, c in days) or 1
    UX, WID = 10.0, 8.5          # week step and bar width (screen x)
    DX, DY = 3.0, -5.0           # weekday step (receding up and right)
    BX, BY = 2.5, -4.5           # bar depth vector
    maxh, pad = 80.0, 14
    W = int(weeks * UX + 7 * DX + 2 * pad)
    caption_space = 32
    H = int(maxh + 7 * -DY + 2 * pad + caption_space)
    base_y0 = pad + maxh + 6 * -DY + caption_space
    css = (TEXT_CSS + "g.b{animation:rise 12s ease-in-out infinite}"
           "@keyframes rise{0%{transform:scaleY(.04)}18%,72%{transform:scaleY(1)}90%,100%{transform:scaleY(.04)}}")
    body = [contribution_caption(days, pad)]
    P = lambda p: "%.1f,%.1f" % p
    for r in range(6, -1, -1):
        for wk in range(weeks):
            if (wk, r) not in cells:
                continue
            d, c = cells[(wk, r)]
            lv = level(c, mx)
            h = 1.5 if c == 0 else 4.0 + (maxh - 4.0) * math.sqrt(c / float(mx))
            col = BLUE[lv] if lv else "#1c2430"
            bx, by = pad + wk * UX + r * DX, base_y0 + r * DY
            top = [(0, -h), (WID, -h), (WID + BX, -h + BY), (BX, -h + BY)]
            front = [(0, 0), (WID, 0), (WID, -h), (0, -h)]
            right = [(WID, 0), (WID + BX, BY), (WID + BX, -h + BY), (WID, -h)]
            delay = -12.0 * (wk / float(weeks)) * 0.85
            body.append('<g transform="translate(%.1f %.1f)"><g class="b" style="animation-delay:%.2fs">'
                        '<polygon points="%s" fill="%s"/><polygon points="%s" fill="%s"/>'
                        '<polygon points="%s" fill="%s"/><title>%s: %d</title></g></g>'
                        % (bx, by, delay, " ".join(map(P, front)), shade_hex(col, 0.75),
                           " ".join(map(P, right)), shade_hex(col, 0.52),
                           " ".join(map(P, top)), col, d, c))
    return svg_wrap(W, H, css, "\n".join(body), "Contribution skyline")


def rotation_index(previous_dir, published_at, now):
    """Advance from the last published design, only after three hours.

    The previous branch commit time is the publication clock. Legacy assets
    without rotation.json are migrated by reading current.svg's title.
    """
    if not previous_dir or not os.path.isfile(os.path.join(previous_dir, "current.svg")):
        return 0
    if not published_at:
        raise ValueError("previous publication time is required")
    previous_time = dt.datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    if previous_time.tzinfo is None:
        raise ValueError("publication time must include a timezone")
    state_path = os.path.join(previous_dir, "rotation.json")
    if os.path.isfile(state_path):
        with open(state_path) as f:
            state = json.load(f)
        name = state["current"]
        if name not in NAMES:
            raise ValueError("unknown previous graph")
    else:
        with open(os.path.join(previous_dir, "current.svg")) as f:
            svg = f.read()
        matches = [name for name in NAMES if "<title>Contribution %s</title>" % name in svg]
        if len(matches) != 1:
            raise ValueError("cannot identify legacy current.svg")
        name = matches[0]
    if now - previous_time < dt.timedelta(hours=3):
        return None
    return (NAMES.index(name) + 1) % len(NAMES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--index", type=int, choices=range(3), help="override rotation index (0 snake, 1 chart, 2 skyline)")
    ap.add_argument("--previous-dir", help="previous assets branch checkout")
    ap.add_argument("--previous-published-at", help="previous assets commit time in ISO format")
    a = ap.parse_args()
    if a.index is not None and a.previous_dir:
        ap.error("--index is for previews and cannot bypass the publication guard")
    now = dt.datetime.now(dt.timezone.utc)
    idx = a.index if a.index is not None else rotation_index(
        a.previous_dir, a.previous_published_at, now)
    if idx is None:
        print("Last publication is less than 3 hours old; nothing to publish.")
        return
    days = get_days(a.user)
    os.makedirs(a.out, exist_ok=True)
    makers = {"snake": make_snake, "chart": make_chart, "skyline": make_skyline}
    for name in NAMES:
        with open(os.path.join(a.out, name + ".svg"), "w") as f:
            f.write(makers[name](days))
    shutil.copyfile(os.path.join(a.out, NAMES[idx] + ".svg"), os.path.join(a.out, "current.svg"))
    with open(os.path.join(a.out, "rotation.json"), "w") as f:
        json.dump({"current": NAMES[idx], "generated_at": now.isoformat()}, f, sort_keys=True)
        f.write("\n")
    print("days=%d total=%d current=%s" % (len(days), sum(c for _, c in days), NAMES[idx]))


if __name__ == "__main__":
    main()
