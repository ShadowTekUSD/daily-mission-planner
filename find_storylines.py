"""
The Daily Mission Planner - Step 4: turn raw stats into storylines.

Usage (from the project folder, with (.venv) active):
    python find_storylines.py 4

Reads data/week_4.json (made by pull_week.py), works out the "news"
(upsets, blowouts, bench blunders, top performers, streaks) and saves
data/storylines_4.json. It also prints the headlines so you can sanity-check.
"""

import json
import sys
from pathlib import Path

NAIL_BITER = 5.0   # margin under this = nail-biter
BLOWOUT = 40.0     # margin over this = blowout
RECENT_TRANSACTIONS = 20  # how many of the newest moves to pass along

# Fill the strict slots first, flex slots last, so the "best possible
# lineup" math comes out right.
SLOT_ORDER = ["QB", "K", "D/ST", "TE", "RB", "WR", "WR/TE", "RB/WR", "RB/WR/TE", "OP"]
OP_POSITIONS = {"QB", "RB", "WR", "TE"}


def eligible(position, slot):
    if slot == "OP":
        return position in OP_POSITIONS
    return position == slot or position in slot.split("/")


def best_possible_score(players):
    """Highest score this roster could have posted with perfect hindsight."""
    slots = [p["slot"] for p in players if p["starter"]]
    slots.sort(key=lambda s: SLOT_ORDER.index(s) if s in SLOT_ORDER else len(SLOT_ORDER))
    pool = [p for p in players if p["slot"] != "IR"]
    used, total = set(), 0.0
    for slot in slots:
        options = [(p["points"], i) for i, p in enumerate(pool)
                   if i not in used and eligible(p["position"], slot)]
        if options:
            pts, i = max(options)
            used.add(i)
            total += pts
    return round(total, 2)


def biggest_bench_mistake(players):
    """The single bench/starter swap that would have gained the most points."""
    starters = [p for p in players if p["starter"]]
    bench = [p for p in players if p["slot"] == "BE"]
    best = None
    for b in bench:
        for s in starters:
            if eligible(b["position"], s["slot"]):
                gain = round(b["points"] - s["points"], 2)
                if gain > 0 and (best is None or gain > best["gain"]):
                    best = {"benched": b["name"], "benched_points": b["points"],
                            "started": s["name"], "started_points": s["points"],
                            "slot": s["slot"], "gain": gain}
    return best


def analyze_matchup(m):
    h, a = m["home"], m["away"]
    winner, loser = (h, a) if h["score"] >= a["score"] else (a, h)
    margin = round(winner["score"] - loser["score"], 2)

    result = {
        "winner": winner["team"], "winner_owner": winner["owner"], "winner_score": winner["score"],
        "loser": loser["team"], "loser_owner": loser["owner"], "loser_score": loser["score"],
        "margin": margin,
        "tie": margin == 0,
        "upset": winner["projected"] < loser["projected"],
        "nail_biter": margin < NAIL_BITER,
        "blowout": margin > BLOWOUT,
        "teams": {},
    }

    for side in (winner, loser):
        starters = sorted([p for p in side["players"] if p["starter"]],
                          key=lambda p: p["points"], reverse=True)
        optimal = best_possible_score(side["players"])
        mistake = biggest_bench_mistake(side["players"])
        result["teams"][side["team"]] = {
            "owner": side["owner"],
            "score": side["score"],
            "projected": side["projected"],
            "beat_projection_by": round(side["score"] - side["projected"], 2),
            "top_starters": [{"name": p["name"], "pos": p["position"], "points": p["points"]}
                             for p in starters[:3]],
            "all_starters": [{"name": p["name"], "pos": p["position"], "slot": p["slot"],
                              "points": p["points"], "projected": p["projected"]}
                             for p in starters],
            "best_bench_players": [{"name": p["name"], "pos": p["position"], "points": p["points"]}
                                   for p in sorted([p for p in side["players"] if p["slot"] == "BE"],
                                                   key=lambda p: p["points"], reverse=True)[:3]],
            "worst_starter": ({"name": starters[-1]["name"], "pos": starters[-1]["position"],
                               "points": starters[-1]["points"]} if starters else None),
            "best_possible_score": optimal,
            "points_left_on_bench": round(optimal - side["score"], 2),
            "biggest_bench_mistake": mistake,
        }

    # Would the loser have won with their best lineup?
    loser_info = result["teams"][loser["team"]]
    result["loser_could_have_won"] = loser_info["best_possible_score"] > winner["score"]
    return result


def main():
    if len(sys.argv) < 2:
        print("Tell me which week, e.g.:  python find_storylines.py 4")
        sys.exit(1)
    week = int(sys.argv[1])

    src = Path("data") / f"week_{week}.json"
    if not src.exists():
        print(f"Can't find {src}. Run:  python pull_week.py {week}")
        sys.exit(1)
    data = json.loads(src.read_text(encoding="utf-8"))

    games = [analyze_matchup(m) for m in data["matchups"]]

    # Attach each team's record, rank and streak so recaps can reference them
    by_team = {s["team"]: s for s in data["standings"]}
    for g in games:
        for team, info in g["teams"].items():
            s = by_team.get(team)
            if s:
                info["record_after_week"] = f"{s['wins']}-{s['losses']}" + (f"-{s['ties']}" if s["ties"] else "")
                info["rank"] = s["rank"]
                info["streak"] = s["streak"]
                info["season_points_for"] = s["points_for"]
                info["playoff_pct"] = s["playoff_pct"]

    # League-wide leaderboards (starters only)
    all_starters = []
    for m in data["matchups"]:
        for side in (m["home"], m["away"]):
            for p in side["players"]:
                if p["starter"]:
                    all_starters.append({**p, "fantasy_team": side["team"], "owner": side["owner"]})
    all_starters.sort(key=lambda p: p["points"], reverse=True)
    skill = [p for p in all_starters if p["position"] in OP_POSITIONS]
    kickers = [p for p in all_starters if p["position"] == "K"]

    def brief(p):
        return {"name": p["name"], "pos": p["position"], "points": p["points"],
                "fantasy_team": p["fantasy_team"], "owner": p["owner"]}

    team_scores = sorted(
        [(t, info["score"]) for g in games for t, info in g["teams"].items()],
        key=lambda x: x[1], reverse=True)

    bench_blunders = sorted(
        [{"team": t, "owner": info["owner"], **info["biggest_bench_mistake"]}
         for g in games for t, info in g["teams"].items() if info["biggest_bench_mistake"]],
        key=lambda x: x["gain"], reverse=True)

    # Pickup of the Week / The One That Got Away
    moves = data.get("week_moves", [])
    adds = sorted([m for m in moves if "ADDED" in m["action"]],
                  key=lambda m: m["week_points"], reverse=True)
    drops = sorted([m for m in moves if m["action"] == "DROPPED"],
                   key=lambda m: m["week_points"], reverse=True)
    pickup_of_week = adds[0] if adds else None
    drop_of_week = drops[0] if drops else None

    storylines = {
        "pickup_of_the_week": pickup_of_week,
        "the_one_that_got_away": drop_of_week,
        "other_notable_adds": adds[1:3],
        "league_name": data["league_name"],
        "season": data["season"],
        "week": week,
        "games": sorted(games, key=lambda g: g["margin"]),  # closest game first
        "highlights": {
            "high_score": {"team": team_scores[0][0], "score": team_scores[0][1]},
            "low_score": {"team": team_scores[-1][0], "score": team_scores[-1][1]},
            "top_players": [brief(p) for p in skill[:5]],
            "biggest_busts": [brief(p) for p in sorted(skill, key=lambda p: p["points"])[:3]],
            "best_kicker": brief(kickers[0]) if kickers else None,
            "bench_blunders": bench_blunders[:3],
            "upsets": [g["winner"] for g in games if g["upset"]],
            "closest_game": games and min(games, key=lambda g: g["margin"])["winner"],
            "biggest_blowout": games and max(games, key=lambda g: g["margin"])["winner"],
        },
        "standings": data["standings"],
        "recent_transactions": data["transactions"][:RECENT_TRANSACTIONS],
    }

    out = Path("data") / f"storylines_{week}.json"
    out.write_text(json.dumps(storylines, indent=2), encoding="utf-8")

    # --- Quick headline printout -------------------------------------------
    hl = storylines["highlights"]
    print(f"\nWeek {week} storylines\n")
    for g in storylines["games"]:
        tags = [t for t, on in (("UPSET", g["upset"]), ("NAIL-BITER", g["nail_biter"]),
                                ("BLOWOUT", g["blowout"])) if on]
        flag = f"  [{', '.join(tags)}]" if tags else ""
        could = "  (loser could have won with best lineup)" if g["loser_could_have_won"] else ""
        print(f"  {g['winner']} beat {g['loser']} by {g['margin']}{flag}{could}")
    print(f"\n  High score: {hl['high_score']['team']} ({hl['high_score']['score']})")
    print(f"  Low score:  {hl['low_score']['team']} ({hl['low_score']['score']})")
    top = hl["top_players"][0]
    print(f"  Top player: {top['name']} ({top['points']}) for {top['fantasy_team']}")
    if hl["bench_blunders"]:
        b = hl["bench_blunders"][0]
        print(f"  Bench blunder: {b['team']} benched {b['benched']} ({b['benched_points']}) "
              f"and started {b['started']} ({b['started_points']})")
    if pickup_of_week:
        p = pickup_of_week
        started = "started him" if p["started_by_team"] else "left him on the bench"
        print(f"  Pickup of the Week: {p['team']} added {p['player']} "
              f"({p['week_points']} pts) and {started}")
    if drop_of_week:
        d = drop_of_week
        print(f"  The One That Got Away: {d['team']} dropped {d['player']} "
              f"({d['week_points']} pts)")
    print(f"\n  Saved to {out}\n")


if __name__ == "__main__":
    main()
