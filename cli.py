import argparse
import json
import sys
from agents.orchestrator import run
from utils.llm_client import extract_text_from_raw


def display_piece(piece: dict, index: int):
    content = piece.get("content", "")
    if content.strip().startswith("{") or content.strip().startswith("["):
        content = extract_text_from_raw(content)
    content = content.replace("\\n", "\n")
    try:
        content = content.encode("utf-8").decode("unicode_escape")
    except Exception:
        pass

    print(f"\n{'=' * 60}")
    print(f"  PIECE {index + 1}")
    print(f"  Type:    {piece.get('type', 'unknown').upper()}")
    print(f"  Title:   {piece.get('title', 'Untitled')}")
    print(f"  Channel: {piece.get('channel', 'Unknown')}")
    print(f"  Words:   {piece.get('meta', {}).get('word_count', 0)}")
    print(f"  CTA:     {piece.get('meta', {}).get('cta', '')}")
    print(f"{'=' * 60}")
    print(content)


def display_scores(critique_output: dict):
    print(f"\n{'=' * 60}")
    print("  CRITIQUE SCORES")
    print(f"{'=' * 60}")
    for s in critique_output.get("scores", []):
        dims = s.get("scores", {})
        print(f"\n  [{s['total']}/100] {s['title']}")
        print(
            f"  Clarity:{dims.get('clarity', 0)}  "
            f"Relevance:{dims.get('relevance', 0)}  "
            f"Conversion:{dims.get('conversion', 0)}  "
            f"Originality:{dims.get('originality', 0)}"
        )
        print(f"  Verdict: {s.get('verdict', '')}")
        for w in s.get("weaknesses", []):
            print(f"  [!] {w}")


def display_rewrite(rewritten: dict):
    print(f"\n{'=' * 60}")
    print("  AUTO-REWRITTEN (lowest scoring piece)")
    print(f"{'=' * 60}")
    display_piece(rewritten, 0)
    changes = rewritten.get("changes", [])
    if changes:
        print("\n  Changes made:")
        for c in changes:
            print(f"  [+] {c}")


def save_output(results: dict, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n  [SAVED] Full output written to {path}")


def main():
    parser = argparse.ArgumentParser(
        description="MarketMind -- AI marketing campaign generator"
    )
    parser.add_argument(
        "--product",
        type=str,
        default=None,
        help="Product description (or omit to use the built-in demo product)",
    )
    parser.add_argument(
        "--goal",
        type=str,
        default="awareness",
        choices=["awareness", "leads", "retention"],
        help="Campaign goal (default: awareness)",
    )
    parser.add_argument(
        "--pieces",
        type=int,
        default=3,
        help="Number of content pieces to generate (default: 3)",
    )
    parser.add_argument(
        "--save",
        type=str,
        default=None,
        help="Optional path to save full JSON output e.g. output.json",
    )
    parser.add_argument(
        "--scores-only",
        action="store_true",
        help="Only show critique scores, skip printing full content",
    )
    args = parser.parse_args()

    product = args.product or """
MarketMind -- a B2B SaaS tool that helps marketing teams at
remote-first startups plan, generate, and iterate on campaign
content using AI agents. Replaces 3-4 separate tools with one
unified workflow.
"""

    print("\n" + "=" * 60)
    print("  MARKETMIND CAMPAIGN GENERATOR")
    print(f"  Goal:   {args.goal}")
    print(f"  Pieces: {args.pieces}")
    print("=" * 60)

    results = run(
        product_description=product,
        campaign_goal=args.goal,
        num_pieces=args.pieces,
        verbose=True,
    )

    meta = results.get("meta", {})
    print(f"\n  Campaign: '{meta.get('campaign_name', '')}'")
    print(f"  Total time: {meta.get('total_time_seconds', 0)}s")

    if not args.scores_only:
        print("\n\n  --- CONTENT PIECES ---")
        for i, piece in enumerate(results["content"]["content"]):
            display_piece(piece, i)

    display_scores(results["critique"])
    display_rewrite(results["critique"]["weakest_rewritten"])

    if args.save:
        save_output(results, args.save)


if __name__ == "__main__":
    main()