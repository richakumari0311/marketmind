import json
from utils.llm_client import chat, parse_json_robust
from utils import memory as mem


SYSTEM_PROMPT = """You are a senior B2B marketing strategist.
You receive market research, past campaign memory, and return a campaign brief.
Return valid JSON only. No extra text, no markdown fences."""


def run(research: dict, campaign_goal: str = "awareness") -> dict:

    # Read memory so we don't repeat campaign names or structures
    memory = mem.load()
    memory_context = mem.format_for_prompt(memory)

    past_campaign_names = [
        c.get("campaign_name", "") for c in memory.get("campaigns", [])
    ]

    prompt = f"""
Create a campaign brief using the research and memory below.
Campaign goal: {campaign_goal}

--- PAST CAMPAIGN MEMORY ---
{memory_context}

--- PAST CAMPAIGN NAMES (do not reuse these) ---
{", ".join(past_campaign_names) if past_campaign_names else "None yet"}

--- RESEARCH ---
{json.dumps(research, indent=2)}

Rules:
- Pick a campaign name that is fresh and different from past names
- Build on winning angles from memory if any exist
- Avoid repeating core messages already used

Return this exact JSON:
{{
  "campaign_name": "fresh punchy campaign name",
  "goal": "{campaign_goal}",
  "core_message": "one sentence the single thing every piece must communicate",
  "channels": [
    {{
      "name": "channel name",
      "priority": "primary or secondary",
      "frequency": "e.g. 3x per week",
      "content_type": "e.g. thought leadership posts"
    }}
  ],
  "messaging_hierarchy": {{
    "headline": "main headline",
    "subheadline": "supporting sentence",
    "proof_points": ["point 1", "point 2", "point 3"],
    "cta": "main call to action"
  }},
  "content_plan": [
    {{
      "week": 1,
      "theme": "week theme",
      "pieces": [
        {{"type": "content type", "title": "specific title", "channel": "channel name"}},
        {{"type": "content type", "title": "specific title", "channel": "channel name"}}
      ]
    }},
    {{
      "week": 2,
      "theme": "week theme",
      "pieces": [
        {{"type": "content type", "title": "specific title", "channel": "channel name"}},
        {{"type": "content type", "title": "specific title", "channel": "channel name"}}
      ]
    }},
    {{
      "week": 3,
      "theme": "week theme",
      "pieces": [
        {{"type": "content type", "title": "specific title", "channel": "channel name"}},
        {{"type": "content type", "title": "specific title", "channel": "channel name"}}
      ]
    }},
    {{
      "week": 4,
      "theme": "week theme",
      "pieces": [
        {{"type": "content type", "title": "specific title", "channel": "channel name"}},
        {{"type": "content type", "title": "specific title", "channel": "channel name"}}
      ]
    }}
  ],
  "kpis": [
    {{"metric": "metric name", "target": "realistic target", "timeframe": "e.g. 30 days"}},
    {{"metric": "metric name", "target": "realistic target", "timeframe": "e.g. 30 days"}},
    {{"metric": "metric name", "target": "realistic target", "timeframe": "e.g. 30 days"}}
  ]
}}
"""

    response = chat(
        messages=[{"role": "user", "content": prompt}],
        system=SYSTEM_PROMPT
    )

    return parse_json_robust(response, context="StrategyAgent")