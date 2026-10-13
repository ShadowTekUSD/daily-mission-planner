"""
The Daily Mission Planner - Step 6: turn the issue into a newspaper page.

Usage (from the project folder, with (.venv) active):
    python make_html.py 4

Reads issues/week_4.md and writes issues/week_4.html, styled like a
newspaper. Double-click the .html file to open it in your browser.
"""

import sys
from datetime import date
from pathlib import Path

import markdown

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Daily Mission Planner - Week {week}</title>
<style>
  body {{
    margin: 0; padding: 24px 16px;
    background: #e9e4d8;
    color: #1b1b1b;
    font-family: Georgia, "Times New Roman", serif;
    font-size: 17px; line-height: 1.6;
  }}
  .paper {{
    max-width: 780px; margin: 0 auto;
    background: #fbf8f1;
    padding: 28px 36px 40px;
    box-shadow: 0 2px 12px rgba(0,0,0,.15);
  }}
  .dateline {{
    display: flex; justify-content: space-between;
    border-top: 3px double #1b1b1b; border-bottom: 1px solid #1b1b1b;
    padding: 4px 0; margin-bottom: 20px;
    font-size: 12px; letter-spacing: .08em; text-transform: uppercase;
  }}
  h1 {{
    font-family: "Old English Text MT", "UnifrakturMaguntia", Georgia, serif;
    font-size: 46px; line-height: 1.1; text-align: center;
    margin: 0 0 6px; font-weight: normal;
  }}
  h1 + p, h1 + p em {{ text-align: center; font-style: italic; color: #555; }}
  h2 {{
    font-size: 15px; letter-spacing: .15em; text-transform: uppercase;
    border-top: 3px solid #1b1b1b; border-bottom: 1px solid #1b1b1b;
    padding: 6px 0; margin: 36px 0 16px; text-align: center;
  }}
  h3 {{
    font-size: 28px; line-height: 1.2; margin: 30px 0 4px;
  }}
  h4 {{
    font-size: 15px; font-style: italic; font-weight: normal;
    color: #444; margin: 0 0 12px;
  }}
  h3 + p::first-letter, h4 + p::first-letter {{
    float: left; font-size: 3.2em; line-height: .9;
    padding: 4px 6px 0 0; font-weight: bold;
  }}
  p {{ margin: 0 0 12px; }}
  strong {{ color: #000; }}
  blockquote {{
    margin: 16px 0; padding: 8px 16px;
    border-left: 4px solid #8b1a1a; background: #f2ece0;
    font-style: italic;
  }}
  blockquote p {{ margin: 0; }}
  ul {{ padding-left: 20px; }}
  li {{ margin-bottom: 6px; }}
  hr {{ border: 0; border-top: 1px dashed #999; margin: 28px 0; }}
  table {{
    width: 100%; border-collapse: collapse; margin: 12px 0 16px;
    font-family: Arial, Helvetica, sans-serif; font-size: 14px;
  }}
  th {{
    text-align: left; border-bottom: 2px solid #1b1b1b;
    padding: 6px 8px; font-size: 12px; text-transform: uppercase;
  }}
  td {{ padding: 6px 8px; border-bottom: 1px solid #d8d0bf; }}
  tr:nth-child(even) td {{ background: #f3eee3; }}
  .footer {{
    margin-top: 36px; padding-top: 10px; border-top: 3px double #1b1b1b;
    font-size: 12px; text-align: center; color: #555;
  }}
  @media (max-width: 600px) {{
    .paper {{ padding: 20px 16px 28px; }}
    h1 {{ font-size: 32px; }}
    .dateline {{ font-size: 10px; letter-spacing: .04em; }}
    .dateline span:nth-child(2) {{ display: none; }}
    h3 {{ font-size: 22px; }}
    table {{ font-size: 12px; }}
    td, th {{ padding: 4px; }}
  }}
</style>
</head>
<body>
  <div class="paper">
    <div class="dateline">
      <span>Week {week} Edition</span>
      <span>{today}</span>
      <span>Price: Your Dignity</span>
    </div>
    {body}
    <div class="footer">
      The Daily Mission Planner &middot; Colby's Lunch Money &middot; Week {week}
    </div>
  </div>
</body>
</html>
"""


def main():
    if len(sys.argv) < 2:
        print("Tell me which week, e.g.:  python make_html.py 4")
        sys.exit(1)
    week = int(sys.argv[1])

    src = Path("issues") / f"week_{week}.md"
    if not src.exists():
        print(f"Can't find {src}. Run:  python write_paper.py {week}")
        sys.exit(1)

    body = markdown.markdown(src.read_text(encoding="utf-8"),
                             extensions=["tables", "sane_lists"])
    page = TEMPLATE.format(week=week, body=body,
                           today=date.today().strftime("%A, %B %d, %Y"))

    out = Path("issues") / f"week_{week}.html"
    out.write_text(page, encoding="utf-8")
    print(f"Saved to {out}  (double-click it to open in your browser)")

    # Publish copy for the website (GitHub Pages serves the docs folder)
    docs = Path("docs")
    docs.mkdir(exist_ok=True)
    (docs / f"week-{week}.html").write_text(page, encoding="utf-8")
    build_index(docs)
    print(f"Published copy saved to docs/week-{week}.html")


def build_index(docs):
    """Front page listing every issue, newest first."""
    weeks = sorted((int(p.stem.split("-")[1]) for p in docs.glob("week-*.html")),
                   reverse=True)
    items = "\n".join(
        f'<li><a href="week-{w}.html">Week {w} Edition</a>'
        + (' <span class="new">LATEST</span>' if i == 0 else "") + "</li>"
        for i, w in enumerate(weeks))
    body = (f"<h1>The Daily Mission Planner</h1>"
            f"<p><em>The Official Paper of Record for Colby's Lunch Money</em></p>"
            f"<h2>The Archives</h2><ul class=\"archive\">{items}</ul>")
    extra = """<style>
  ul.archive {{ list-style: none; padding: 0; font-size: 20px; }}
  ul.archive li {{ padding: 10px 0; border-bottom: 1px solid #d8d0bf; }}
  ul.archive a {{ color: #1b1b1b; }}
  .new {{ font: bold 11px Arial, sans-serif; background: #8b1a1a; color: #fff;
          padding: 2px 6px; margin-left: 8px; vertical-align: middle; }}
</style>"""
    latest = weeks[0] if weeks else 0
    page = TEMPLATE.format(week=latest, body=body,
                           today=date.today().strftime("%A, %B %d, %Y"))
    page = page.replace("</head>", extra.replace("{{", "{").replace("}}", "}") + "\n</head>", 1)
    page = page.replace(f"<span>Week {latest} Edition</span>", "<span>Est. 2026</span>", 1)
    (docs / "index.html").write_text(page, encoding="utf-8")


if __name__ == "__main__":
    main()
