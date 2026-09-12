"""Typeset a neofetch of the profile, from what GitHub will tell you about it.

Everything else in the README is written once and then stands still. This block
is the one part that answers for itself: how long the account has been open,
how much is public, what was pushed last and into what. It is drawn by the same
typesetter as the rest, in the same two inks, so it reads as another line of
the page rather than as a badge bolted onto it.

The REST API is enough for all of it and needs no scope beyond public data -
`GITHUB_TOKEN` is used when it is there only to buy the larger rate limit
inside Actions.

Run from the repo root: python .build/live.py
"""

import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import textsvg  # noqa: E402  - the path has to be set before this resolves

USER = "PersusUS"
API = "https://api.github.com"
WINDOW = 30           # days the push count looks back over
TOP_LANGUAGES = 4     # how many of them make it into the line
NARROW_COLS = 36      # columns a value is folded to in the phone variant

# A notebook's byte count is mostly base64 of the pictures it printed, so a
# repo with a handful of them buries every language actually written by hand.
NOT_A_LANGUAGE = {"Jupyter Notebook"}


def get(path):
    """One GET against the API, as JSON."""
    req = urllib.request.Request(API + path, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": USER + "-profile",
    })
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=30) as fh:
        return json.load(fh)


def days_open(user):
    opened = dt.datetime.strptime(user["created_at"], "%Y-%m-%dT%H:%M:%SZ")
    return (dt.datetime.utcnow() - opened).days


def languages(repos):
    """Bytes per language across every public repo that is not a fork.

    A repo's own /languages is asked for one at a time. If that runs into the
    rate limit, the coarse `language` field each repo already carries is used
    instead, which names the majority language and nothing else.
    """
    total = {}
    try:
        for repo in repos:
            for name, size in get("/repos/%s/languages" % repo["full_name"]).items():
                total[name] = total.get(name, 0) + size
    except urllib.error.HTTPError:
        total = {}
        for repo in repos:
            if repo["language"]:
                total[repo["language"]] = total.get(repo["language"], 0) + repo["size"]
    return {k: v for k, v in total.items() if k not in NOT_A_LANGUAGE}


def share(total, n=TOP_LANGUAGES):
    """The top few languages as percentages of the whole, largest first."""
    if not total:
        return "-"
    whole = float(sum(total.values()))
    top = sorted(total.items(), key=lambda kv: -kv[1])[:n]
    return " / ".join("%s %d%%" % (name, round(100 * size / whole))
                      for name, size in top)


def pushes(events):
    """The last push, and how many pushes fall inside the window.

    Pushes, not commits: the public events feed no longer carries the commit
    count in its payload, and a number that cannot be checked is worse than a
    smaller one that can.
    """
    edge = dt.datetime.utcnow() - dt.timedelta(days=WINDOW)
    last, count = None, 0
    for ev in events:
        if ev["type"] != "PushEvent":
            continue
        when = dt.datetime.strptime(ev["created_at"], "%Y-%m-%dT%H:%M:%SZ")
        if last is None:
            last = (ev["repo"]["name"], when)
        if when >= edge:
            count += 1
    return last, count


def rows(user, repos, events):
    """The block, as label-and-value pairs, one baseline each."""
    last, count = pushes(events)
    pushed = "%s - %s" % (last[0], last[1].strftime("%d %b %Y")) if last else "-"
    return [
        ("UPTIME", "%d days since the account opened" % days_open(user)),
        ("REPOS", "%d public" % user["public_repos"]),
        ("PUSHED", pushed),
        ("LANGUAGES", share(languages(repos))),
        ("PUSHES", "%d in the last %d days" % (count, WINDOW)),
    ]


def main():
    user = get("/users/" + USER)
    repos = [r for r in get("/users/%s/repos?per_page=100&type=owner" % USER)
             if not r["fork"]]
    events = get("/users/%s/events/public?per_page=100" % USER)
    lines = rows(user, repos, events)

    col = max(len(label) for label, _ in lines) + 3
    textsvg.svg([[(label.ljust(col), textsvg.FG), (value, textsvg.DIM)]
                 for label, value in lines],
                "s-fetch", size=25.6, leading=1.3)
    # On a phone the value goes under its label, the way the stack block does.
    narrow = []
    for label, value in lines:
        narrow.append([(label, textsvg.FG)])
        narrow.extend([("  " + part, textsvg.DIM)] for part in textsvg.fold(value, NARROW_COLS))
    textsvg.svg(narrow, "s-fetch-n", size=21, leading=1.3)


if __name__ == "__main__":
    main()
