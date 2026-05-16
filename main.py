from agents.orchestrator import run

result = run(
    product_description="""
MarketMind -- a B2B SaaS tool that helps marketing teams at
remote-first startups plan, generate, and iterate on campaign
content using AI agents. Replaces 3-4 separate tools with one
unified workflow.
""",
    campaign_goal="awareness",
    num_pieces=3,
    verbose=True,
)

print(f"\nDone. Campaign: '{result['meta']['campaign_name']}'")
print(f"Total time: {result['meta']['total_time_seconds']}s")
print(f"Memory run #{result['meta']['memory_run']}")