import os
from datetime import datetime
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

_client = Client(auth=os.getenv("NOTION_API_KEY"))
PARENT_PAGE_ID = os.getenv("NOTION_PAGE_ID", "")


def _text(content: str) -> dict:
    return {"type": "text", "text": {"content": str(content)[:2000]}}


def _heading(text: str, level: int = 2) -> dict:
    tag = f"heading_{level}"
    return {
        "object": "block",
        "type": tag,
        tag: {"rich_text": [_text(text)]}
    }


def _paragraph(text: str) -> dict:
    clean = str(text).replace("\\n", "\n")[:2000]
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [_text(clean)]}
    }


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _callout(text: str, emoji: str = "i") -> dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [_text(text)],
            "icon": {"type": "emoji", "emoji": emoji},
        }
    }


def _bullet(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": [_text(str(text)[:2000])]}
    }


def _toggle(title: str, children: list) -> dict:
    return {
        "object": "block",
        "type": "toggle",
        "toggle": {
            "rich_text": [_text(title)],
            "children": children[:100],
        }
    }


def _append(page_id: str, blocks: list):
    for i in range(0, len(blocks), 100):
        _client.blocks.children.append(
            block_id=page_id,
            children=blocks[i:i+100]
        )


def write_campaign(results: dict) -> str:
    """
    Write a full campaign result to Notion.
    Creates a child page under PARENT_PAGE_ID.
    Returns the URL of the created page.
    """
    if not PARENT_PAGE_ID:
        print("  [WARN] NOTION_PAGE_ID not set, skipping Notion write")
        return ""

    strategy = results.get("strategy", {})
    research = results.get("research", {})
    content  = results.get("content", {})
    critique = results.get("critique", {})
    meta     = results.get("meta", {})

    campaign_name = strategy.get("campaign_name", "Campaign")
    date          = meta.get("date", datetime.now().strftime("%Y-%m-%d %H:%M"))
    goal          = meta.get("goal", "awareness")
    avg_score     = meta.get("avg_score", 0)

    page = _client.pages.create(
        parent={"type": "page_id", "page_id": PARENT_PAGE_ID},
        properties={
            "title": {
                "title": [_text(f"{campaign_name} -- {date}")]
            }
        }
    )
    page_id  = page["id"]
    page_url = page.get("url", "")

    blocks = []

    blocks.append(_callout(
        f"Goal: {goal.upper()}  |  Avg Score: {avg_score}/100  |  {date}",
        emoji="rocket"
    ))
    blocks.append(_divider())

    blocks.append(_heading("Core Message", 2))
    blocks.append(_paragraph(strategy.get("core_message", "")))

    mh = strategy.get("messaging_hierarchy", {})
    if mh:
        blocks.append(_heading("Messaging Hierarchy", 2))
        blocks.append(_paragraph(f"Headline: {mh.get('headline','')}"))
        blocks.append(_paragraph(f"Subheadline: {mh.get('subheadline','')}"))
        blocks.append(_paragraph(f"CTA: {mh.get('cta','')}"))
        for point in mh.get("proof_points", []):
            blocks.append(_bullet(point))

    audience = research.get("target_audience", {})
    if audience:
        blocks.append(_divider())
        blocks.append(_heading("Target Audience", 2))
        blocks.append(_paragraph(f"Primary: {audience.get('primary','')}"))
        blocks.append(_paragraph(f"Secondary: {audience.get('secondary','')}"))
        blocks.append(_paragraph(f"Company size: {audience.get('company_size','')}"))
        for title in audience.get("job_titles", []):
            blocks.append(_bullet(title))

    pain_points = research.get("pain_points", [])
    if pain_points:
        blocks.append(_heading("Pain Points", 2))
        for p in pain_points:
            blocks.append(_bullet(p))

    competitors = research.get("competitors", [])
    if competitors:
        blocks.append(_heading("Competitors", 2))
        for c in competitors:
            blocks.append(_bullet(
                f"{c.get('name','')} -- {c.get('weakness','')}"
            ))

    kpis = strategy.get("kpis", [])
    if kpis:
        blocks.append(_divider())
        blocks.append(_heading("KPIs", 2))
        for k in kpis:
            blocks.append(_bullet(
                f"{k.get('metric','')} -- {k.get('target','')} ({k.get('timeframe','')})"
            ))

    content_plan = strategy.get("content_plan", [])
    if content_plan:
        blocks.append(_divider())
        blocks.append(_heading("4-Week Content Plan", 2))
        for week in content_plan:
            week_children = []
            for piece in week.get("pieces", []):
                week_children.append(_bullet(
                    f"{piece.get('type','').upper()} -- {piece.get('title','')} ({piece.get('channel','')})"
                ))
            blocks.append(_toggle(
                f"Week {week.get('week','')} -- {week.get('theme','')}",
                week_children
            ))

    scores = critique.get("scores", [])
    if scores:
        blocks.append(_divider())
        blocks.append(_heading("Critique Scores", 2))
        for s in scores:
            dims = s.get("scores", {})
            blocks.append(_bullet(
                f"[{s.get('total',0)}/100] {s.get('title','')} -- "
                f"Clarity:{dims.get('clarity',0)} "
                f"Relevance:{dims.get('relevance',0)} "
                f"Conversion:{dims.get('conversion',0)} "
                f"Originality:{dims.get('originality',0)}"
            ))
            blocks.append(_paragraph(s.get("verdict", "")))

    pieces = content.get("content", [])
    if pieces:
        blocks.append(_divider())
        blocks.append(_heading("Content Pieces", 2))
        for piece in pieces:
            text  = str(piece.get("content", "")).replace("\\n", "\n")
            cta   = piece.get("meta", {}).get("cta", "")
            words = piece.get("meta", {}).get("word_count", 0)

            piece_children = [
                _paragraph(f"Channel: {piece.get('channel','')} | Words: {words}"),
                _paragraph(text[:2000]),
            ]
            if cta:
                piece_children.append(_callout(f"CTA: {cta}", emoji="link"))

            blocks.append(_toggle(
                f"{piece.get('type','').upper()} -- {piece.get('title','Untitled')}",
                piece_children
            ))

    rewritten = critique.get("weakest_rewritten")
    if rewritten:
        blocks.append(_divider())
        blocks.append(_heading("Auto-Rewritten Piece", 2))
        rw_text = str(rewritten.get("content", "")).replace("\\n", "\n")

        rw_children = [_paragraph(rw_text[:2000])]
        for c in rewritten.get("changes", []):
            rw_children.append(_bullet(f"[+] {c}"))

        blocks.append(_toggle(
            f"Rewritten: {rewritten.get('title','Untitled')}",
            rw_children
        ))

    _append(page_id, blocks)

    print(f"  [NOTION] Campaign written to: {page_url}")
    return page_url