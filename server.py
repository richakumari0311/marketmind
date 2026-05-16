import asyncio
import json
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel

from agents.research_agent import run as research
from agents.strategy_agent import run as strategy
from agents.content_agent import run as write_content
from agents.critique_agent import run as critique
from utils import memory as mem

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


class CampaignRequest(BaseModel):
    product: str
    goal: str = "awareness"
    pieces: int = 3


@app.get("/")
def index():
    return FileResponse("static/index.html")


@app.post("/run")
async def run_campaign(req: CampaignRequest):

    async def stream():
        loop = asyncio.get_event_loop()

        def emit(event_type: str, data: dict):
            return {"event": event_type, "data": json.dumps(data)}

        research_output = None
        strategy_output = None
        content_output = None

        # --- Phase 1: Research ---
        try:
            yield emit("progress", {"phase": 1, "label": "ResearchAgent", "status": "running"})
            research_output = await loop.run_in_executor(None, research, req.product)
            yield emit("progress", {"phase": 1, "label": "ResearchAgent", "status": "done"})
            yield emit("research", research_output)
        except Exception as e:
            yield emit("progress", {"phase": 1, "label": "ResearchAgent", "status": "error"})
            yield emit("error", {"phase": 1, "message": f"ResearchAgent failed: {str(e)}"})
            return

        # --- Phase 2: Strategy ---
        try:
            yield emit("progress", {"phase": 2, "label": "StrategyAgent", "status": "running"})
            strategy_output = await loop.run_in_executor(
                None, lambda: strategy(research_output, campaign_goal=req.goal)
            )
            yield emit("progress", {"phase": 2, "label": "StrategyAgent", "status": "done"})
            yield emit("strategy", strategy_output)
        except Exception as e:
            yield emit("progress", {"phase": 2, "label": "StrategyAgent", "status": "error"})
            yield emit("error", {"phase": 2, "message": f"StrategyAgent failed: {str(e)}"})
            return

        # --- Phase 3: Content ---
        try:
            yield emit("progress", {"phase": 3, "label": "ContentAgent", "status": "running"})
            content_output = await loop.run_in_executor(
                None, lambda: write_content(strategy_output, max_pieces=req.pieces)
            )
            yield emit("progress", {"phase": 3, "label": "ContentAgent", "status": "done"})
            yield emit("content", content_output)
        except Exception as e:
            yield emit("progress", {"phase": 3, "label": "ContentAgent", "status": "error"})
            yield emit("error", {"phase": 3, "message": f"ContentAgent failed: {str(e)}"})
            # Strategy still succeeded so show what we have
            yield emit("done", {
                "campaign_name": strategy_output.get("campaign_name", ""),
                "partial": True
            })
            return

        # --- Phase 4: Critique ---
        try:
            yield emit("progress", {"phase": 4, "label": "CritiqueAgent", "status": "running"})
            critique_output = await loop.run_in_executor(
                None, lambda: critique(content_output, strategy_output)
            )
            yield emit("progress", {"phase": 4, "label": "CritiqueAgent", "status": "done"})
            yield emit("critique", critique_output)
        except Exception as e:
            yield emit("progress", {"phase": 4, "label": "CritiqueAgent", "status": "error"})
            yield emit("error", {"phase": 4, "message": f"CritiqueAgent failed: {str(e)}"})
            # Content still succeeded, show done without critique
            yield emit("done", {
                "campaign_name": strategy_output.get("campaign_name", ""),
                "partial": True
            })
            return
        
# --- Save to memory after full successful run ---
        try:
            mem.record_campaign(
                product=req.product,
                campaign_name=strategy_output.get("campaign_name", ""),
                research=research_output,
                strategy=strategy_output,
                scores=critique_output.get("scores", []),
            )
        except Exception as e:
            print(f"  [WARN] Memory save failed: {e}")

        yield emit("done", {
            "campaign_name": strategy_output.get("campaign_name", ""),
            "partial": False,
            "total_runs": mem.load().get("total_runs", 0),
        })

    return EventSourceResponse(stream())