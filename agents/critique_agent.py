import json
from utils.llm_client import chat, parse_json_robust


SYSTEM_PROMPT = """You are a senior B2B marketing critic and editor.
You evaluate content ruthlessly but constructively.
Return valid JSON only. No extra text, no markdown fences."""


SCORE_DIMENSIONS = [
    "clarity",       # Is the message immediately clear?
    "relevance",     # Does it speak to the target audience?
    "conversion",    # Does it drive toward the CTA?
    "originality",   # Does it avoid cliches and generic phrases?
]


def _score_piece(piece: dict, strategy: dict) -> dict:
    """Score a single content piece across 4 dimensions."""

    prompt = f"""
You are evaluating a B2B marketing content piece.

Campaign goal: {strategy['core_message']}
Target audience: Marketing managers at remote-first startups
CTA: {strategy['messaging_hierarchy']['cta']}

Content piece:
Type: {piece['type']}
Title: {piece['title']}
Channel: {piece['channel']}
Content:
{piece['content'][:1500]}

Score this piece on each dimension from 1 to 10.
Be strict. A 7 means genuinely good. A 10 is rare.

Return this exact JSON:
{{
  "type": "{piece['type']}",
  "title": "{piece['title']}",
  "scores": {{
    "clarity": 0,
    "relevance": 0,
    "conversion": 0,
    "originality": 0
  }},
  "total": 0,
  "strengths": ["strength 1", "strength 2"],
  "weaknesses": ["weakness 1", "weakness 2"],
  "verdict": "one sentence overall verdict"
}}

Set total to the average of all 4 scores multiplied by 10 (so 0-100 scale).
"""

    response = chat(
        messages=[{"role": "user", "content": prompt}],
        system=SYSTEM_PROMPT
    )

    result = parse_json_robust(response, context="CritiqueAgent [score]")

    # Recalculate total ourselves to not trust the model's math
    scores = result.get("scores", {})
    values = [scores.get(d, 0) for d in SCORE_DIMENSIONS]
    result["total"] = round((sum(values) / len(values)) * 10, 1)

    return result


def _rewrite_piece(piece: dict, critique: dict, strategy: dict) -> dict:
    """Rewrite the weakest piece based on critique feedback."""

    weaknesses = "\n".join(f"- {w}" for w in critique.get("weaknesses", []))

    prompt = f"""
Rewrite this content piece to fix the identified weaknesses.

Original content:
Type: {piece['type']}
Title: {piece['title']}
Channel: {piece['channel']}
Content: {piece['content'][:1500]}

Weaknesses to fix:
{weaknesses}

Campaign context:
Core message: {strategy['core_message']}
Headline: {strategy['messaging_hierarchy']['headline']}
CTA: {strategy['messaging_hierarchy']['cta']}
Audience: Marketing managers at remote-first startups

Instructions:
- Fix every weakness listed above
- Keep the same content type and channel
- Keep roughly the same length
- Make the opening hook stronger
- Make the CTA more specific and urgent
- Cut any generic marketing cliches

IMPORTANT: Return only a single valid JSON object.
Escape all newlines as \\n inside string values.
The "content" field MUST be a single plain string.

{{
  "type": "{piece['type']}",
  "title": "improved title if needed",
  "channel": "{piece['channel']}",
  "content": "full rewritten content as one string with \\n for line breaks",
  "meta": {{
    "word_count": 0,
    "cta": "the specific CTA used"
  }},
  "changes": ["change made 1", "change made 2", "change made 3"]
}}
"""

    response = chat(
        messages=[{"role": "user", "content": prompt}],
        system=SYSTEM_PROMPT
    )

    result = parse_json_robust(response, context="CritiqueAgent [rewrite]")

    content = result.get("content", "")
    if isinstance(content, list):
        content = "\n".join(str(item) for item in content)
    elif not isinstance(content, str):
        content = str(content)
    result["content"] = content

    if "meta" not in result or not isinstance(result["meta"], dict):
        result["meta"] = {"word_count": 0, "cta": strategy["messaging_hierarchy"]["cta"]}

    result["meta"]["word_count"] = len(result["content"].split())
    return result


def run(content_pack: dict, strategy: dict) -> dict:
    """
    Takes content pack from ContentAgent and strategy from StrategyAgent.
    Scores all pieces, rewrites the lowest scorer.
    Returns critique report + improved content pack.
    """

    pieces = content_pack.get("content", [])
    print(f"  Scoring {len(pieces)} pieces...")

    scored = []
    for i, piece in enumerate(pieces):
        print(f"  [{i+1}/{len(pieces)}] Scoring: {piece.get('title', 'Untitled')}")
        critique = _score_piece(piece, strategy)
        scored.append({"piece": piece, "critique": critique})

    # Find the weakest piece
    weakest = min(scored, key=lambda x: x["critique"]["total"])
    weakest_title = weakest["piece"].get("title", "Untitled")
    weakest_score = weakest["critique"]["total"]

    print(f"\n  Weakest piece (score {weakest_score}/100): {weakest_title}")
    print(f"  Rewriting...")

    rewritten = _rewrite_piece(weakest["piece"], weakest["critique"], strategy)

    # Replace the weakest piece in the content pack
    improved_content = []
    for item in scored:
        if item["piece"].get("title") == weakest["piece"].get("title"):
            improved_content.append(rewritten)
        else:
            improved_content.append(item["piece"])

    return {
        "campaign_name": content_pack["campaign_name"],
        "scores": [
            {
                "title": s["piece"].get("title"),
                "type": s["piece"].get("type"),
                "total": s["critique"]["total"],
                "scores": s["critique"]["scores"],
                "verdict": s["critique"].get("verdict", ""),
                "weaknesses": s["critique"].get("weaknesses", []),
            }
            for s in scored
        ],
        "weakest_rewritten": rewritten,
        "improved_content": improved_content,
    }