"""
MemoryMap RAG Evaluation Runner

Runs the full evaluation pipeline:
1. Loads ground truth queries
2. Runs each query through keyword retriever AND Gemini retriever
3. Computes all IR metrics (Recall@K, MRR, MAP, nDCG@K, etc.)
4. Prints a comparison table and saves results to JSON

Usage:
    cd backend
    python -m evaluation.run_eval
    # Or with flags:
    python -m evaluation.run_eval --skip-gemini   # keyword-only (no API cost)
    python -m evaluation.run_eval --verbose        # show per-query details
"""

import asyncio
import argparse
import json
import time
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Add parent dir to path so we can import services
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv()

from evaluation.ground_truth import MOCK_HOME_TAGS, GROUND_TRUTH_QUERIES
from evaluation.metrics import compute_all_metrics, aggregate_metrics
from evaluation.retriever import (
    keyword_retrieve,
    gemini_retrieve,
    gemini_answer_and_extract_tags,
)


def print_table(headers: list[str], rows: list[list], col_width: int = 14):
    """Print a formatted ASCII table."""
    header_line = " | ".join(h.center(col_width) for h in headers)
    separator = "-+-".join("-" * col_width for _ in headers)
    print(header_line)
    print(separator)
    for row in rows:
        formatted = []
        for val in row:
            if isinstance(val, float):
                formatted.append(f"{val:.4f}".center(col_width))
            else:
                formatted.append(str(val).center(col_width))
        print(" | ".join(formatted))


async def run_evaluation(skip_gemini: bool = False, verbose: bool = False):
    """Run the full RAG evaluation."""
    print("=" * 70)
    print("  MemoryMap RAG Evaluation")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Queries: {len(GROUND_TRUTH_QUERIES)}")
    print(f"  Tags in mock DB: {len(MOCK_HOME_TAGS)}")
    print(f"  Retrievers: keyword" + ("" if skip_gemini else " + gemini + end-to-end"))
    print("=" * 70)

    results = {
        "timestamp": datetime.now().isoformat(),
        "num_queries": len(GROUND_TRUTH_QUERIES),
        "num_tags": len(MOCK_HOME_TAGS),
        "keyword": {"per_query": [], "aggregate": {}},
    }
    if not skip_gemini:
        results["gemini_ranker"] = {"per_query": [], "aggregate": {}}
        results["gemini_e2e"] = {"per_query": [], "aggregate": {}}

    keyword_all = []
    gemini_ranker_all = []
    gemini_e2e_all = []

    for i, gt in enumerate(GROUND_TRUTH_QUERIES):
        query = gt["query"]
        relevant_ids = gt["relevant_tag_ids"]

        if verbose:
            print(f"\n--- Query {i+1}: \"{query}\"")
            print(f"    Relevant: {relevant_ids}")

        # 1. Keyword retriever
        kw_retrieved = keyword_retrieve(query, MOCK_HOME_TAGS)
        kw_metrics = compute_all_metrics(kw_retrieved, relevant_ids)
        keyword_all.append(kw_metrics)
        results["keyword"]["per_query"].append({
            "query": query,
            "retrieved_top5": kw_retrieved[:5],
            **kw_metrics,
        })

        if verbose:
            print(f"    Keyword top-5: {kw_retrieved[:5]}")
            print(f"    Keyword RR={kw_metrics['reciprocal_rank']:.3f} "
                  f"R@1={kw_metrics['recall@1']:.3f} "
                  f"R@3={kw_metrics['recall@3']:.3f} "
                  f"nDCG@5={kw_metrics['ndcg@5']:.3f}")

        # 2. Gemini ranker
        if not skip_gemini:
            try:
                gm_retrieved = await gemini_retrieve(query, MOCK_HOME_TAGS)
                gm_metrics = compute_all_metrics(gm_retrieved, relevant_ids)
                gemini_ranker_all.append(gm_metrics)
                results["gemini_ranker"]["per_query"].append({
                    "query": query,
                    "retrieved_top5": gm_retrieved[:5],
                    **gm_metrics,
                })
                if verbose:
                    print(f"    Gemini ranker top-5: {gm_retrieved[:5]}")
                    print(f"    Gemini RR={gm_metrics['reciprocal_rank']:.3f} "
                          f"R@1={gm_metrics['recall@1']:.3f} "
                          f"R@3={gm_metrics['recall@3']:.3f} "
                          f"nDCG@5={gm_metrics['ndcg@5']:.3f}")
            except Exception as e:
                print(f"    [WARN] Gemini ranker failed: {e}")
                gemini_ranker_all.append(compute_all_metrics([], relevant_ids))

            # 3. End-to-end (answer + extract tags — simulates production)
            try:
                answer, e2e_referenced = await gemini_answer_and_extract_tags(
                    query, MOCK_HOME_TAGS
                )
                e2e_metrics = compute_all_metrics(e2e_referenced, relevant_ids)
                gemini_e2e_all.append(e2e_metrics)
                results["gemini_e2e"]["per_query"].append({
                    "query": query,
                    "answer": answer[:200],
                    "referenced_tags": e2e_referenced,
                    **e2e_metrics,
                })
                if verbose:
                    print(f"    E2E answer: {answer[:100]}...")
                    print(f"    E2E referenced: {e2e_referenced}")
            except Exception as e:
                print(f"    [WARN] Gemini E2E failed: {e}")
                gemini_e2e_all.append(compute_all_metrics([], relevant_ids))

            # Brief pause to avoid rate limiting
            await asyncio.sleep(0.5)

    # Aggregate
    kw_agg = aggregate_metrics(keyword_all)
    results["keyword"]["aggregate"] = kw_agg

    retrievers = [("Keyword", kw_agg)]

    if not skip_gemini and gemini_ranker_all:
        gm_agg = aggregate_metrics(gemini_ranker_all)
        results["gemini_ranker"]["aggregate"] = gm_agg
        retrievers.append(("Gemini Ranker", gm_agg))

    if not skip_gemini and gemini_e2e_all:
        e2e_agg = aggregate_metrics(gemini_e2e_all)
        results["gemini_e2e"]["aggregate"] = e2e_agg
        retrievers.append(("Gemini E2E", e2e_agg))

    # Print results table
    print("\n" + "=" * 70)
    print("  AGGREGATED RESULTS (averaged across all queries)")
    print("=" * 70)

    metrics_to_show = [
        ("MRR", "MRR"),
        ("MAP", "MAP"),
        ("Recall@1", "mean_recall@1"),
        ("Recall@3", "mean_recall@3"),
        ("Recall@5", "mean_recall@5"),
        ("Recall@10", "mean_recall@10"),
        ("Precision@1", "mean_precision@1"),
        ("Precision@3", "mean_precision@3"),
        ("Precision@5", "mean_precision@5"),
        ("nDCG@1", "mean_ndcg@1"),
        ("nDCG@3", "mean_ndcg@3"),
        ("nDCG@5", "mean_ndcg@5"),
        ("nDCG@10", "mean_ndcg@10"),
        ("Hit Rate@1", "mean_hit_rate@1"),
        ("Hit Rate@3", "mean_hit_rate@3"),
        ("Hit Rate@5", "mean_hit_rate@5"),
    ]

    headers = ["Metric"] + [name for name, _ in retrievers]
    rows = []
    for display_name, key in metrics_to_show:
        row = [display_name]
        for _, agg in retrievers:
            row.append(agg.get(key, 0.0))
        rows.append(row)

    print_table(headers, rows, col_width=16)

    # Category breakdown
    print("\n" + "=" * 70)
    print("  RESULTS BY CATEGORY")
    print("=" * 70)

    categories = set(gt["category"] for gt in GROUND_TRUTH_QUERIES)
    for cat in sorted(categories):
        cat_indices = [i for i, gt in enumerate(GROUND_TRUTH_QUERIES) if gt["category"] == cat]
        cat_kw = [keyword_all[i] for i in cat_indices]
        cat_kw_agg = aggregate_metrics(cat_kw)

        print(f"\n  {cat} ({len(cat_indices)} queries):")
        print(f"    Keyword  — MRR: {cat_kw_agg.get('MRR', 0):.3f}  "
              f"R@1: {cat_kw_agg.get('mean_recall@1', 0):.3f}  "
              f"R@3: {cat_kw_agg.get('mean_recall@3', 0):.3f}  "
              f"nDCG@5: {cat_kw_agg.get('mean_ndcg@5', 0):.3f}")

        if not skip_gemini and gemini_ranker_all:
            cat_gm = [gemini_ranker_all[i] for i in cat_indices]
            cat_gm_agg = aggregate_metrics(cat_gm)
            print(f"    Gemini   — MRR: {cat_gm_agg.get('MRR', 0):.3f}  "
                  f"R@1: {cat_gm_agg.get('mean_recall@1', 0):.3f}  "
                  f"R@3: {cat_gm_agg.get('mean_recall@3', 0):.3f}  "
                  f"nDCG@5: {cat_gm_agg.get('mean_ndcg@5', 0):.3f}")

    # Save results
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "eval_results.json"
    )
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nFull results saved to: {output_path}")

    return results


def main():
    parser = argparse.ArgumentParser(description="MemoryMap RAG Evaluation")
    parser.add_argument("--skip-gemini", action="store_true",
                        help="Skip Gemini-based retrievers (keyword only, no API cost)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show per-query details")
    args = parser.parse_args()

    asyncio.run(run_evaluation(skip_gemini=args.skip_gemini, verbose=args.verbose))


if __name__ == "__main__":
    main()
