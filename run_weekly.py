"""
The Daily Mission Planner - Step 8: the weekly autopilot.

Works out which week just finished, then runs every step:
pull -> storylines -> write -> HTML. GitHub runs this every Tuesday.

You can also run it yourself:
    python run_weekly.py          # figures out the week on its own
    python run_weekly.py 5        # a specific week
    python run_weekly.py 5 force  # re-do a week that's already published
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from espn_api.football import League

PACIFIC = ZoneInfo("America/Los_Angeles")
PUBLISH_HOUR = 8  # 8 a.m. Pacific


def last_finished_week():
    """The most recent NFL week whose games are all done.

    ESPN may or may not have flipped to the next week by early Tuesday
    morning, so instead of trusting its "current week" we check whether
    every game in that week has actually been played.
    """
    load_dotenv()
    league = League(
        league_id=int(os.environ["LEAGUE_ID"]),
        year=int(os.environ["SEASON"]),
        espn_s2=os.environ["ESPN_S2"],
        swid=os.environ["SWID"],
    )
    week = league.current_week
    for box in league.box_scores(week=week):
        for side in (box.home_lineup, box.away_lineup):
            for p in side or []:
                if not getattr(p, "on_bye_week", False) and getattr(p, "game_played", 100) < 100:
                    return week - 1  # games still to play, so last week is the finished one
    return week


def run(*args):
    print(f"\n>>> python {' '.join(args)}", flush=True)
    subprocess.run([sys.executable, *args], check=True)


def main():
    args = sys.argv[1:]
    force = "force" in args
    week_args = [a for a in args if a.isdigit()]
    scheduled = os.environ.get("GITHUB_EVENT_NAME") == "schedule"

    # GitHub's clock is UTC and ignores daylight saving, so the schedule
    # fires twice; only the run at/after 8 a.m. Pacific does the work.
    if scheduled and datetime.now(PACIFIC).hour < PUBLISH_HOUR:
        print("Before 8 a.m. Pacific - nothing to do yet.")
        return

    week = int(week_args[0]) if week_args else last_finished_week()
    if week < 1:
        print("No finished week yet.")
        return

    if Path("docs", f"week-{week}.html").exists() and not force:
        print(f"Week {week} is already published. Nothing to do.")
        return

    print(f"Publishing Week {week}")
    run("pull_week.py", str(week))
    run("find_storylines.py", str(week))
    run("write_paper.py", str(week))
    run("make_html.py", str(week))

    # Hand the week number to the GitHub workflow for the commit message
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"week={week}\n")


if __name__ == "__main__":
    main()
