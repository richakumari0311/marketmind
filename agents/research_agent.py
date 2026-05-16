import os
import json
from utils.llm_client import chat, parse_json_robust
from utils.tools import web_search, scrape_page, format_search_results
from utils import memory as mem


SYSTEM_PROMPT = """You are an expert B2B market research analyst.
You receive real search results and past campaign memory.
Use both to produce accurate, non-repetitive research.
Return valid JSON only. No extra text, no markdown fences."""


def _gather_intel(product_description: str) -> dict:
    """
    Run targeted searches to gather real market intelligence.
    """
    print("    Searching: competitors...")
    competitor_results = web_search(
        f"top competitors alternatives to {product_description[:80]} B2B SaaS",
        num_results=5
    )

    print("    Searching: market trends...")
    trend_results = web_search(
        f"B2B marketing automation AI content tools trends 2025 2026",
        num_results=5
    )

    print("    Searching: pain points...")
    pain_results = web_search(
        f"marketing team content workflow problems pain points remote startup",
        num_results=4
    )

    deep_info = ""
    if competitor_results and competitor_results[0].get("link"):
        print(f"    Scraping: {competitor_results[0]['link'][:60]}...")
        deep_info = scrape_page(competitor_results[0]["link"])

    return {
        "competitors": format_search_results(competitor_results),
        "trends":      format_search_results(trend_results),
        "pain_points": format_search_results(pain_results),
        "deep_info":   deep_info[:1500] if deep_info else "",
    }


def run(product_description: str) -> dict:
    """
    Takes a product description.
    Reads memory, searches the web, returns structured research.
    """

    # Step 1 -- load memory
    memory = mem.load()
    memory_context = mem.format_for_prompt(memory)

    # Step 2 -- gather real data
    print("  Gathering live market intelligence...")
    intel = _gather_intel(product_description)

    # Step 3 -- reason on real data + memory
    prompt = f"""
Analyze this product using both memory of past campaigns and fresh web research.

Product:
{product_description}

--- MEMORY OF PAST CAMPAIGNS ---
{memory_context}

--- REAL COMPETITOR DATA (from web search) ---
{intel['competitors']}

--- REAL MARKET TRENDS (from web search) ---
{intel['trends']}

--- REAL CUSTOMER PAIN POINTS (from web search) ---
{intel['pain_points']}

--- ADDITIONAL CONTEXT ---
{intel['deep_info'] if intel['deep_info'] else 'None available.'}

Instructions:
- Use REAL competitor names from the search results above
- Do NOT repeat messaging angles already used in past campaigns
- Do NOT repeat hooks listed in memory
- Build on what worked well previously
- If competitors are already known from memory, focus on finding new ones

Return this exact JSON:
{{
  "target_audience": {{
    "primary": "one sentence describing the main buyer",
    "secondary": "one sentence describing a secondary buyer",
    "company_size": "e.g. 10-200 employees",
    "job_titles": ["title1", "title2", "title3"]
  }},
  "pain_points": [
    "pain point 1 (cite real source if possible)",
    "pain point 2",
    "pain point 3",
    "pain point 4"
  ],
  "competitors": [
    {{"name": "Real Competitor from search", "weakness": "specific weakness"}},
    {{"name": "Real Competitor from search", "weakness": "specific weakness"}},
    {{"name": "Real Competitor from search", "weakness": "specific weakness"}}
  ],
  "positioning": {{
    "unique_value": "one clear differentiating sentence",
    "category": "product category",
    "tone": "e.g. professional, bold, empathetic"
  }},
  "messaging_angles": [
    {{"angle": "NEW angle not used before", "hook": "NEW hook not used before"}},
    {{"angle": "NEW angle not used before", "hook": "NEW hook not used before"}},
    {{"angle": "NEW angle not used before", "hook": "NEW hook not used before"}}
  ],
  "sources": ["URL or source name used"]
}}
"""

    response = chat(
        messages=[{"role": "user", "content": prompt}],
        system=SYSTEM_PROMPT
    )

    return parse_json_robust(response, context="ResearchAgent")