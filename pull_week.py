"""
The Daily Mission Planner - Step 3: pull one week of league data from ESPN.

Usage (from the project folder, with (.venv) active):
    python pull_week.py 4

Saves everything to data/week_4.json and prints a quick scoreboard
so you can check it against ESPN.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from espn_api.football import League

STARTER_EXCLUDE = {"BE", "IR"}  # bench and injured reserve don't count


def owner_name(team):
    """Return the owner's display name, whatever format ESPN sends it in."""
    if not team.owners:
        return "Unknown"
    o = team.owners[0]
    if isinstance(o, dict):
        first = o.get("firstName", "")
        last = o.get("lastName", "")
        return f"{first} {last}".strip() or o.get("displayName", "Unknown")
    return str(o)


def player_rows(lineup):
    rows = []
    for p in lineup:
        rows.append({
            "name": p.name,
            "position": p.position,
            "slot": p.slot_position,
            "nfl_team": p.proTeam,
            "points": round(p.points or 0, 2),
            "projected": round(p.projected_points or 0, 2),
            "starter": p.slot_position not in STARTER_EXCLUDE,
            "on_bye": getattr(p, "on_bye_week", False),
        })
    return rows


def team_side(team, score, projected, lineup):
    return {
        "team": team.team_name,
        "abbrev": team.team_abbrev,
        "owner": owner_name(team),
        "score": round(score, 2),
        "projected": round(projected or 0, 2),
        "players": player_rows(lineup),
    }


def main():
    if len(sys.argv) < 2:
        print("Tell me which week, e.g.:  python pull_week.py 4")
        sys.exit(1)
    week = int(sys.argv[1])

    load_dotenv()
    league = League(
        league_id=int(os.environ["LEAGUE_ID"]),
        year=int(os.environ["SEASON"]),
        espn_s2=os.environ["ESPN_S2"],
        swid=os.environ["SWID"],
    )

    # --- Matchups -----------------------------------------------------------
    matchups = []
    game_dates = []
    for box in league.box_scores(week=week):
        if box.home_team == 0 or box.away_team == 0:
            continue  # bye week placeholder
        for p in box.home_lineup + box.away_lineup:
            if getattr(p, "game_date", None):
                game_dates.append(p.game_date)
        matchups.append({
            "home": team_side(box.home_team, box.home_score,
                              box.home_projected, box.home_lineup),
            "away": team_side(box.away_team, box.away_score,
                              box.away_projected, box.away_lineup),
        })

    # --- Standings ----------------------------------------------------------
    standings = []
    for t in league.standings():
        standings.append({
            "rank": t.standing,
            "team": t.team_name,
            "owner": owner_name(t),
            "wins": t.wins,
            "losses": t.losses,
            "ties": t.ties,
            "points_for": round(t.points_for, 2),
            "points_against": round(t.points_against, 2),
            "streak": f"{t.streak_type[:1]}{t.streak_length}" if t.streak_type else "",
            "playoff_pct": t.playoff_pct,
            "moves": t.acquisitions,
        })

    # --- Recent transactions -----------------------------------------------
    transactions = []
    for act in league.recent_activity(size=50):
        when = datetime.fromtimestamp(act.date / 1000).strftime("%a %b %d %I:%M %p")
        for entry in act.actions:
            # ESPN sometimes adds extra fields (like a waiver bid); we only need the first three
            team, action, player = entry[0], entry[1], entry[2]
            transactions.append({
                "date": when,
                "timestamp": act.date,
                "team": team.team_name if hasattr(team, "team_name") else str(team),
                "action": action,
                "player": getattr(player, "name", str(player)),
                "player_id": getattr(player, "playerId", None),
            })

    # --- Pickups and drops that mattered this week --------------------------
    # The "waiver window" for this week is the 7 days before its last game
    # (usually Monday night). A player added in that window and how he
    # scored this week is what Pickup of the Week is built from.
    moves = []
    if game_dates:
        window_end = max(game_dates)
        window_start = window_end - timedelta(days=7)
        in_window = [t for t in transactions
                     if t["player_id"] and window_start.timestamp() * 1000
                     <= t["timestamp"] <= window_end.timestamp() * 1000]

        # Look up every moved player's points for this week in one request
        ids = sorted({t["player_id"] for t in in_window})
        week_points = {}
        if ids:
            found = league.player_info(playerId=ids)
            if found and not isinstance(found, list):
                found = [found]
            for pl in found or []:
                week_points[pl.playerId] = round(
                    pl.stats.get(week, {}).get("points", 0), 2)

        # Who started him this week (if anyone)?
        lineup_slot = {}
        for m in matchups:
            for side in (m["home"], m["away"]):
                for p in side["players"]:
                    lineup_slot[(side["team"], p["name"])] = p["slot"]

        for t in in_window:
            slot = lineup_slot.get((t["team"], t["player"]))
            moves.append({
                "date": t["date"],
                "team": t["team"],
                "action": t["action"],
                "player": t["player"],
                "week_points": week_points.get(t["player_id"], 0),
                "started_by_team": slot not in (None, "BE", "IR") if "ADDED" in t["action"] else None,
            })

    data = {
        "league_name": league.settings.name,
        "season": league.year,
        "week": week,
        "matchups": matchups,
        "standings": standings,
        "transactions": transactions,
        "week_moves": moves,
    }

    Path("data").mkdir(exist_ok=True)
    out = Path("data") / f"week_{week}.json"
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # --- Quick check printout ----------------------------------------------
    print(f"\n{data['league_name']} - Week {week}\n")
    for m in matchups:
        h, a = m["home"], m["away"]
        print(f"  {a['team']:<28} {a['score']:>7}   @   {h['team']:<28} {h['score']:>7}")
    print(f"\n  {len(standings)} teams in standings, {len(transactions)} transactions pulled")
    print(f"  {len(moves)} adds/drops in this week's waiver window")
    print(f"  Saved to {out}\n")


if __name__ == "__main__":
    main()
