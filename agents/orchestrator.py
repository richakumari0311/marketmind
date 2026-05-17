import time
from datetime import datetime
from agents.research_agent import run as research
from agents.strategy_agent import run as strategy
from agents.content_agent import run as write_content
from agents.critique_agent import run as critique
from utils import memory as mem
from utils.notion_writer import write_campaign


def run(
    product_description: str,
    campaign_goal: str = "awareness",
    num_pieces: int = 3,
    verbose: bool = True,
) -> dict:

    def log(msg):
        if verbose:
            print(msg)

    start = time.time()
    results = {}

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    log("\n[1/4] Research...")
    t0 = time.time()
    results["research"] = research(product_description)
    log(f"      done ({round(time.time() - t0, 1)}s)")

    log("[2/4] Strategy...")
    t0 = time.time()
    results["strategy"] = strategy(results["research"], campaign_goal=campaign_goal)
    log(f"      done ({round(time.time() - t0, 1)}s) -- campaign: '{results['strategy']['campaign_name']}'")

    log("[3/4] Writing content...")
    t0 = time.time()
    results["content"] = write_content(results["strategy"], max_pieces=num_pieces)
    log(f"      done ({round(time.time() - t0, 1)}s) -- {results['content']['total_pieces']} pieces written")

    log("[4/4] Critiquing and rewriting...")
    t0 = time.time()
    results["critique"] = critique(results["content"], results["strategy"])
    log(f"      done ({round(time.time() - t0, 1)}s)")

    avg_score = round(
        sum(s.get("total", 0) for s in results["critique"].get("scores", [])) /
        max(len(results["critique"].get("scores", [])), 1), 1
    )

    results["meta"] = {
        "run_id":             run_id,
        "product":            product_description.strip(),
        "goal":               campaign_goal,
        "date":               datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_time_seconds": round(time.time() - start, 1),
        "campaign_name":      results["strategy"]["campaign_name"],
        "pieces_generated":   num_pieces,
        "avg_score":          avg_score,
        "memory_run":         mem.load().get("total_runs", 0) + 1,
    }

    log("[MEM] Saving to memory...")
    mem.record_campaign(
        product=product_description,
        campaign_name=results["strategy"].get("campaign_name", ""),
        research=results["research"],
        strategy=results["strategy"],
        scores=results["critique"].get("scores", []),
    )

    mem.save_campaign_file(run_id, results)

    log("[NOTION] Writing to Notion...")
    try:
        notion_url = write_campaign(results)
        results["meta"]["notion_url"] = notion_url
    except Exception as e:
        print(f"  [WARN] Notion write failed: {e}")
        results["meta"]["notion_url"] = ""

    return results