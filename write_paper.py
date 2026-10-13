"""
The Daily Mission Planner - Step 5: have Claude write the issue.

Usage (from the project folder, with (.venv) active):
    python write_paper.py 4

Reads data/storylines_4.json and league_bible.md and has Claude write the
issue one piece at a time: one call per game, then one call for everything
else. Writing in pieces means no game can get skipped or cut off.
Saves the finished issue to issues/week_4.md.
"""

import json
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

MODEL = "claude-sonnet-5-5"   # good writing, a few cents per issue
MAX_TOKENS = 8000             # per piece; one game recap is well under this

STYLE = """You write for The Daily Mission Planner, the weekly newspaper of a \
fantasy football league. Think SportsCenter: every game gets its own highlight-show \
treatment, delivered by anchors who love the sport and love roasting the people who \
play it badly.

ACCURACY RULES (non-negotiable):
- Use only the numbers, names and facts in the data you are given. Never invent \
stats, plays, injuries, or events. Talk in fantasy points unless the data gives more.
- Fake quotes are fine when obviously played for laughs and attributed to an unnamed \
"team source", "sideline reporter" or "a fan in the parking lot", never put in a real \
owner's mouth as if they actually said it.
- A starter who scored 0 may have been injured, inactive or on bye. Roast the goose \
egg; don't claim a reason the data doesn't show.
- Fantasy teams are the "teams"; owners are the "coaches", "GMs" or "front office".

TONE: HEAVY TRASH TALK
- Bring the heat. Losing teams get roasted, and winners get needled too if they won \
ugly, got lucky, or benched points of their own. Sarcasm, mock outrage, fake \
investigations, "sources say", over-the-top hype and dramatic disappointment are all \
fair game.
- Targets: lineup decisions, benched studs, zero-point starters, panic drops, losing \
streaks, low scores, kickers outscoring stars, teams that won only because their \
opponent was worse, playoff odds.
- It's friends ribbing friends: sharp, never cruel. Roast the football, not the person. \
Never joke about anyone's real job, family, looks, money, relationships, health or \
anything personal. Follow every rule in the League Bible.

Keep paragraphs short and punchy. Output only the requested Markdown, with no \
preamble or notes to the editor."""

GAME_TASK = """Write the SportsCenter-style recap for this ONE game, in this exact \
Markdown format:

### <punchy headline>
#### <trash-talking sub-headline that includes the final score>

<4-6 short paragraphs: how it was won, the stars, the duds, the turning-point lineup \
decision, and what it means for both teams' records and streaks.>

**Top Play:** <the best individual performance in this game>

**Not Top 10:** <the worst decision or performance in this game, roasted>

**Postgame Pressers:**

> <fake quote from the winning side's "team source">

> <fake quote from the losing side's "team source">

Use the exact team names "{winner}" and "{loser}" at least once each."""

EXTRAS_TASK = """The game recaps are already written. Write the REST of this week's \
issue in this exact Markdown format:

# The Daily Mission Planner
*<league name> · Week <n> · <one-line teaser of the week's biggest storyline>*

## Pickup of the Week
<who was added, how he scored, whether his new team started him; praise or mockery>

## The One That Got Away
<who was dropped, how he scored for nobody, roast the team that cut him>

## Week Awards
<one line each, each with a jab: Player of the Week, Bench Blunder, Bust of the Week, \
Kicker of the Week, Team of the Week, Toilet Bowl Watch>

## Standings
<Markdown table: Rk | Team | Record | PF | Streak, all 12 teams>
<2-3 sentences on the playoff picture>

## Transaction Wire
<brief, snarky notes on the most interesting recent moves>

---
*<one-line sign-off>*

Put the line ===GAMES=== on its own line right after the teaser line, so the game \
recaps can be slotted in there."""


def write_piece(client, bible, data, task, required_names):
    """One Claude call, retried once if it's cut off or misses a team."""
    prompt = (f"<league_bible>\n{bible}\n</league_bible>\n\n"
              f"<data>\n{json.dumps(data, indent=2)}\n</data>\n\n{task}")
    text, problems = "", []
    for attempt in (1, 2):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=STYLE,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        problems = []
        if response.stop_reason == "max_tokens":
            problems.append("ran too long and got cut off")
        missing = [n for n in required_names if n not in text]
        if missing:
            problems.append(f"didn't mention {', '.join(missing)}")
        if not problems:
            return text, response.usage.output_tokens
        print(f"    Problem: {'; '.join(problems)}." + (" Retrying..." if attempt == 1 else ""))
    raise RuntimeError("; ".join(problems))


def main():
    if len(sys.argv) < 2:
        print("Tell me which week, e.g.:  python write_paper.py 4")
        sys.exit(1)
    week = int(sys.argv[1])

    load_dotenv()

    src = Path("data") / f"storylines_{week}.json"
    if not src.exists():
        print(f"Can't find {src}. Run:  python find_storylines.py {week}")
        sys.exit(1)
    storylines = json.loads(src.read_text(encoding="utf-8"))

    bible_path = Path("league_bible.md")
    bible = bible_path.read_text(encoding="utf-8") if bible_path.exists() else "(none)"

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from .env
    games = storylines["games"]     # already ordered most dramatic first
    total_out = 0

    try:
        # 1. One recap per game
        recaps = []
        for i, g in enumerate(games, 1):
            print(f"  Writing game {i} of {len(games)}: {g['winner']} vs {g['loser']}")
            context = {
                "week": week,
                "this_game": g,
                "week_highlights": storylines["highlights"],
                "standings": storylines["standings"],
            }
            task = GAME_TASK.format(winner=g["winner"], loser=g["loser"])
            text, used = write_piece(client, bible, context, task, [g["winner"], g["loser"]])
            recaps.append(text)
            total_out += used

        # 2. Masthead, pickups, awards, standings, transactions
        print("  Writing awards, standings and the rest")
        extras_data = {k: v for k, v in storylines.items() if k != "games"}
        extras_data["final_scores"] = [
            f"{g['winner']} {g['winner_score']} def. {g['loser']} {g['loser_score']}"
            for g in games]
        extras, used = write_piece(client, bible, extras_data, EXTRAS_TASK, ["===GAMES==="])
        total_out += used
    except RuntimeError as err:
        print(f"\nWARNING: the issue couldn't be finished ({err}). Nothing was published.")
        sys.exit(1)  # stops the automatic run so a bad issue never gets published

    # 3. Assemble: masthead, then every game, then everything else
    game_section = ("\n\n## Game Recaps\n\n" + "\n\n---\n\n".join(recaps)
                    + "\n\n---\n\n")
    issue = extras.replace("===GAMES===", game_section, 1)

    Path("issues").mkdir(exist_ok=True)
    out = Path("issues") / f"week_{week}.md"
    out.write_text(issue, encoding="utf-8")
    print(f"Done. Saved to {out}  ({total_out:,} tokens written)")


if __name__ == "__main__":
    main()
