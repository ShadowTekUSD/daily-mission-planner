"""
The Daily Mission Planner - Step 5: have Claude write the issue.

Usage (from the project folder, with (.venv) active):
    python write_paper.py 4

Reads data/storylines_4.json and league_bible.md, sends them to Claude,
and saves the finished issue to issues/week_4.md.
"""

import json
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

MODEL = "claude-sonnet-5-5"   # good writing, a few cents per issue
MAX_TOKENS = 20000

SYSTEM_PROMPT = """You are the entire staff of The Daily Mission Planner, the weekly \
newspaper of a fantasy football league. Think SportsCenter: every game gets its own \
highlight-show treatment, delivered by anchors who love the sport and love roasting \
the people who play it badly.

ACCURACY RULES (non-negotiable):
- Use only the numbers, names and facts in the data you are given. Never invent \
stats, plays, injuries, or events. You may describe what the numbers imply (e.g. \
"two rushing TDs" only if the data shows them; otherwise talk about points).
- Fake quotes are fine when obviously played for laughs and attributed to an unnamed \
"team source", "sideline reporter" or "a fan in the parking lot", never put in a real \
owner's mouth as if they actually said it.
- A starter who scored 0 may have been injured, inactive or on bye. Roast the goose \
egg; don't claim a reason the data doesn't show.
- Fantasy teams are the "teams"; owners are the "coaches", "GMs" or "front office".

TONE: HEAVY TRASH TALK
- Bring the heat. Every losing team gets roasted, and winners get needled too if they \
won ugly, got lucky, or benched points of their own. Sarcasm, mock outrage, fake \
investigations, "sources say", over-the-top hype and dramatic disappointment are all \
fair game.
- Targets: lineup decisions, benched studs, zero-point starters, panic drops, losing \
streaks, low scores, kickers outscoring stars, teams that won only because their \
opponent was worse, playoff odds.
- It's friends ribbing friends: sharp, never cruel. Roast the football, not the person. \
Never joke about anyone's real job, family, looks, money, relationships, health or \
anything personal. Follow every rule in the League Bible.
- Spread it around. Everyone gets got eventually; nobody is the punchline of every section.

STRUCTURE (Markdown):
1. Masthead: paper name, league name, week number, plus a one-line teaser of the \
week's biggest storyline.
2. GAME RECAPS: every matchup gets a full SportsCenter-style segment, ordered from \
most dramatic to least (upsets, nail-biters and "could have won" games first). Each:
   - A punchy headline and a trash-talking sub-headline with the final score.
   - 4-6 short paragraphs: how it was won, the stars, the duds, the turning-point \
lineup decision, and what it means for both records and streaks.
   - "Top Play": the best individual performance in the game.
   - "Not Top 10": the worst decision or performance, roasted.
   - "Postgame Pressers": one fake quote from each side's "team source".
3. Pickup of the Week and The One That Got Away: who was added and dropped, how they \
scored, and appropriate praise or mockery.
4. Week Awards: Player of the Week, Bench Blunder, Bust of the Week, Kicker of the \
Week, Team of the Week, Toilet Bowl Watch. One line each, each with a jab.
5. Standings: a table with rank, team, record, points for, streak, then 2-3 sentences \
of commentary on the playoff picture.
6. Transaction Wire: brief, snarky notes on the most interesting recent moves.
7. A one-line sign-off.

MARKDOWN FORMAT (the page layout depends on it):
- "# The Daily Mission Planner" once at the top, then one italic line for the teaser.
- "## " for each section name (Game Recaps, Pickup of the Week, etc.).
- "### " for each game's headline and "#### " for its sub-headline with the score.
- Put each Postgame Presser quote on its own line starting with "> ".
- "---" between games.

Keep paragraphs short and punchy. The whole issue should take 6-8 minutes to read."""


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

    # Spell out every game so none gets skipped
    games = storylines["games"]
    checklist = "\n".join(
        f"{i}. {g['winner']} {g['winner_score']} vs {g['loser']} {g['loser_score']}"
        for i, g in enumerate(games, 1))

    user_message = (
        f"<league_bible>\n{bible}\n</league_bible>\n\n"
        f"<week_{week}_data>\n{json.dumps(storylines, indent=2)}\n</week_{week}_data>\n\n"
        f"Write this week's issue of The Daily Mission Planner. There are {len(games)} "
        f"games this week and EVERY one must get its own full recap, including blowouts:\n"
        f"{checklist}"
    )

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from .env
    issue, missing = "", []
    for attempt in (1, 2):
        print(f"Writing the Week {week} issue... (this takes 1-2 minutes)")
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        issue = "".join(b.text for b in response.content if b.type == "text")
        usage = response.usage
        print(f"  ({usage.input_tokens:,} tokens in, {usage.output_tokens:,} tokens out)")

        # Quality check: did it finish, and does every team appear?
        cut_off = response.stop_reason == "max_tokens"
        missing = [t for g in games for t in (g["winner"], g["loser"]) if t not in issue]
        if not cut_off and not missing:
            break
        if cut_off:
            print("  The issue ran too long and got cut off.")
        if missing:
            print(f"  These teams weren't covered: {', '.join(missing)}")
        if attempt == 1:
            print("  Trying once more...")

    Path("issues").mkdir(exist_ok=True)
    out = Path("issues") / f"week_{week}.md"
    out.write_text(issue, encoding="utf-8")
    print(f"Done. Saved to {out}")
    if missing:
        print("  WARNING: still missing some teams. Check the issue before sending it.")
        sys.exit(1)  # stops the automatic run so a bad issue never gets published


if __name__ == "__main__":
    main()
