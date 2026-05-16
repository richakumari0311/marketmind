import json
from utils.llm_client import chat, parse_json_robust


SYSTEM_PROMPT = """You are an expert B2B content writer.
You write clear, engaging, conversion-focused content for marketing teams.
Return valid JSON only. No extra text, no markdown fences."""


def _write_piece(piece: dict, strategy: dict) -> dict:

    type_instructions = {
        "blog post": "Write a full blog post with an intro, 3 sections with subheadings, and a conclusion. Aim for 400-500 words.",
        "blog posts": "Write a full blog post with an intro, 3 sections with subheadings, and a conclusion. Aim for 400-500 words.",
        "thought leadership post": "Write a LinkedIn post. Hook in the first line, no hashtag spam, conversational but expert tone. 150-200 words.",
        "thought leadership posts": "Write a LinkedIn post. Hook in the first line, no hashtag spam, conversational but expert tone. 150-200 words.",
        "email newsletter": "Write a marketing email with subject line, preview text, body (150-200 words), and a clear CTA button label.",
        "email newsletters": "Write a marketing email with subject line, preview text, body (150-200 words), and a clear CTA button label.",
        "video tutorial": "Write a video script outline with intro hook, 3 key sections, and a closing CTA. 200-250 words.",
    }

    piece_type    = piece.get("type", "blog post")
    piece_title   = piece.get("title", "Untitled")
    piece_channel = piece.get("channel", piece.get("platform", "Blog"))

    instructions = type_instructions.get(
        piece_type,
        "Write engaging marketing content appropriate for the channel."
    )

    prompt = f"""
Campaign: {strategy['campaign_name']}
Core message: {strategy['core_message']}
Headline: {strategy['messaging_hierarchy']['headline']}
CTA: {strategy['messaging_hierarchy']['cta']}
Tone: Professional but approachable
Audience: Marketing managers and content strategists at remote startups

Content to write:
- Type: {piece_type}
- Title: {piece_title}
- Channel: {piece_channel}

Instructions: {instructions}

IMPORTANT: Return only a single valid JSON object.
Escape all newlines as \\n inside string values.
The "content" field MUST be a single plain string, not a list or array.
Use this exact structure:
{{
  "type": "{piece_type}",
  "title": "{piece_title}",
  "channel": "{piece_channel}",
  "content": "full written content here as one string with \\n for line breaks",
  "meta": {{
    "word_count": 0,
    "cta": "the specific CTA used in this piece"
  }}
}}
"""

    response = chat(
        messages=[{"role": "user", "content": prompt}],
        system=SYSTEM_PROMPT
    )

    try:
        result = parse_json_robust(response, context=f"ContentAgent [{piece_type}]")
    except ValueError as e:
        print(f"  [WARN] Falling back to raw text: {e}")
        result = {
            "type": piece_type,
            "title": piece_title,
            "channel": piece_channel,
            "content": response.strip(),
            "meta": {
                "word_count": 0,
                "cta": strategy["messaging_hierarchy"]["cta"]
            }
        }

    content = result.get("content", "")
    if isinstance(content, list):
        content = "\n".join(str(item) for item in content)
    elif not isinstance(content, str):
        content = str(content)
    result["content"] = content

    if "meta" not in result or not isinstance(result["meta"], dict):
        result["meta"] = {
            "word_count": 0,
            "cta": strategy["messaging_hierarchy"]["cta"]
        }

    result["meta"]["word_count"] = len(result["content"].split())
    return result


def run(strategy: dict, max_pieces: int = 3) -> dict:
    all_pieces = []
    for week in strategy.get("content_plan", []):
        for piece in week.get("pieces", []):
            enriched = dict(piece)
            enriched["week"] = week.get("week", 0)
            enriched["theme"] = week.get("theme", "")
            all_pieces.append(enriched)

    to_write = all_pieces[:max_pieces]

    print(f"  Writing {len(to_write)} content pieces...")
    written = []
    for i, piece in enumerate(to_write):
        piece_type  = piece.get("type", "unknown")
        piece_title = piece.get("title", "Untitled")
        print(f"  [{i+1}/{len(to_write)}] {piece_type}: {piece_title}")
        written.append(_write_piece(piece, strategy))

    return {
        "campaign_name": strategy["campaign_name"],
        "total_pieces": len(written),
        "content": written
    }