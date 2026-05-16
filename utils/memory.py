import json
import os
from datetime import datetime

MEMORY_FILE = "memory.json"
MAX_CAMPAIGNS = 10  # keep last N campaigns to avoid prompt bloat


def load() -> dict:
    """Load memory from disk. Returns empty structure if no file yet."""
    if not os.path.exists(MEMORY_FILE):
        return {
            "campaigns": [],
            "brand_voice": "",
            "winning_angles": [],
            "used_hooks": [],
            "known_competitors": [],
            "total_runs": 0,
        }
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  [WARN] Could not load memory: {e}")
        return {}


def save(memory: dict):
    """Write memory to disk."""
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"  [WARN] Could not save memory: {e}")


def record_campaign(
    product: str,
    campaign_name: str,
    research: dict,
    strategy: dict,
    scores: list[dict],
):
    """
    After a run completes, extract what's worth remembering and save it.
    Called from the orchestrator after all agents finish.
    """
    memory = load()

    # Figure out the best scoring piece this run
    best = max(scores, key=lambda s: s.get("total", 0)) if scores else {}
    worst = min(scores, key=lambda s: s.get("total", 0)) if scores else {}

    # Extract messaging angles used this run
    angles = [
        a.get("angle", "") for a in
        research.get("messaging_angles", [])
    ]

    # Extract hooks used
    hooks = [
        a.get("hook", "") for a in
        research.get("messaging_angles", [])
    ]

    # Extract competitors found this run
    competitors = [
        c.get("name", "") for c in
        research.get("competitors", [])
    ]

    # Build a compact campaign record
    record = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "product": product[:200],
        "campaign_name": campaign_name,
        "goal": strategy.get("goal", ""),
        "core_message": strategy.get("core_message", ""),
        "tone": research.get("positioning", {}).get("tone", ""),
        "angles_used": angles,
        "hooks_used": hooks,
        "competitors_found": competitors,
        "best_piece": {
            "title": best.get("title", ""),
            "type": best.get("type", ""),
            "score": best.get("total", 0),
        },
        "worst_piece": {
            "title": worst.get("title", ""),
            "score": worst.get("total", 0),
            "weaknesses": worst.get("weaknesses", []),
        },
        "avg_score": round(
            sum(s.get("total", 0) for s in scores) / len(scores), 1
        ) if scores else 0,
    }

    # Update running memory
    memory["total_runs"] = memory.get("total_runs", 0) + 1
    memory["campaigns"] = ([record] + memory.get("campaigns", []))[:MAX_CAMPAIGNS]

    # Accumulate winning angles (score >= 70)
    if record["avg_score"] >= 70:
        for angle in angles:
            if angle and angle not in memory.get("winning_angles", []):
                memory.setdefault("winning_angles", []).append(angle)

    # Track all hooks ever used (to avoid repeats)
    for hook in hooks:
        if hook and hook not in memory.get("used_hooks", []):
            memory.setdefault("used_hooks", []).append(hook)

    # Accumulate known competitors
    for c in competitors:
        if c and c not in memory.get("known_competitors", []):
            memory.setdefault("known_competitors", []).append(c)

    save(memory)
    print(f"  [MEMORY] Run #{memory['total_runs']} saved to {MEMORY_FILE}")


def format_for_prompt(memory: dict) -> str:
    """
    Format memory into a concise context block for agent prompts.
    Keeps it short -- agents don't need the full history, just key signals.
    """
    if not memory or not memory.get("total_runs"):
        return "No previous campaigns. This is the first run."

    lines = [
        f"Total campaigns run: {memory.get('total_runs', 0)}",
    ]

    # Last campaign summary
    campaigns = memory.get("campaigns", [])
    if campaigns:
        last = campaigns[0]
        lines.append(f"\nMost recent campaign: '{last['campaign_name']}' ({last['date']})")
        lines.append(f"Goal: {last.get('goal', '')} | Avg score: {last.get('avg_score', 0)}/100")
        lines.append(f"Core message used: {last.get('core_message', '')}")

    # Winning angles
    winning = memory.get("winning_angles", [])
    if winning:
        lines.append(f"\nAngles that scored well previously:")
        for a in winning[:5]:
            lines.append(f"  - {a}")

    # Hooks to avoid repeating
    used_hooks = memory.get("used_hooks", [])
    if used_hooks:
        lines.append(f"\nHooks already used (avoid repeating):")
        for h in used_hooks[-6:]:
            lines.append(f"  - {h}")

    # Known competitors (skip re-researching these)
    known = memory.get("known_competitors", [])
    if known:
        lines.append(f"\nCompetitors already identified: {', '.join(known[:8])}")

    return "\n".join(lines)