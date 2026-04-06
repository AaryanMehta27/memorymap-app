"""
MemoryMap RAG Evaluation Runner

Runs the full evaluation pipeline:
1. Loads ground truth queries
2. Runs each query through ALL retriever strategies:
   - Keyword (baseline)
   - TF-IDF + Cosine Similarity (custom vectors, L2 normalized)
   - BM25 (probabilistic retrieval)
   - Co-occurrence Embeddings via SVD (dense vectors)
   - Gemini Ranker (LLM-based, optional)
   - Gemini E2E (production simulation, optional)
3. Computes all IR metrics (Recall@K, MRR, MAP, nDCG@K, etc.)
4. Prints a comparison table and saves results to JSON

Usage:
    cd backend
    python -m evaluation.run_eval                    # all retrievers
    python -m evaluation.run_eval --skip-gemini      # custom only (no API cost)
    python -m evaluation.run_eval --verbose           # show per-query details
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
from evaluation.embeddings import (
    TfIdfRetriever,
    BM25Retriever,
    EmbeddingRetriever,
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

    retriever_names = ["Keyword", "TF-IDF", "BM25", "SVD Embed"]
    if not skip_gemini:
        retriever_names += ["Gemini Ranker", "Gemini E2E"]

    print("=" * 70)
    print("  MemoryMap RAG Evaluation")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Queries: {len(GROUND_TRUTH_QUERIES)}")
    print(f"  Tags in mock DB: {len(MOCK_HOME_TAGS)}")
    print(f"  Retrievers: {', '.join(retriever_names)}")
    print("=" * 70)

    # ---- Fit custom retrievers on the tag corpus ----
    print("\n  Fitting custom retrievers...")

    t0 = time.time()
    tfidf_retriever = TfIdfRetriever().fit(MOCK_HOME_TAGS)
    print(f"    TF-IDF: vocab_size={tfidf_retriever.vectorizer.vocab_size}, "
          f"fitted in {time.time()-t0:.3f}s")

    t0 = time.time()
    bm25_retriever = BM25Retriever(k1=1.5, b=0.75).fit(MOCK_HOME_TAGS)
    print(f"    BM25: k1=1.5, b=0.75, fitted in {time.time()-t0:.3f}s")

    t0 = time.time()
    embed_retriever = EmbeddingRetriever(embedding_dim=32).fit(MOCK_HOME_TAGS)
    print(f"    SVD Embeddings: dim=32, vocab_size={len(embed_retriever.embedder.vocabulary)}, "
          f"fitted in {time.time()-t0:.3f}s")

    # ---- Initialize results storage ----
    results = {
        "timestamp": datetime.now().isoformat(),
        "num_queries": len(GROUND_TRUTH_QUERIES),
        "num_tags": len(MOCK_HOME_TAGS),
    }

    all_metrics = {name: [] for name in retriever_names}
    per_query_results = {name: [] for name in retriever_names}

    # ---- Run evaluation queries ----
    print(f"\n  Running {len(GROUND_TRUTH_QUERIES)} queries...\n")

    for i, gt in enumerate(GROUND_TRUTH_QUERIES):
        query = gt["query"]
        relevant_ids = gt["relevant_tag_ids"]

        if verbose:
            print(f"  --- Query {i+1}: \"{query}\"")
            print(f"      Relevant: {relevant_ids}")

        # 1. Keyword retriever
        kw_retrieved = keyword_retrieve(query, MOCK_HOME_TAGS)
        kw_metrics = compute_all_metrics(kw_retrieved, relevant_ids)
        all_metrics["Keyword"].append(kw_metrics)
        per_query_results["Keyword"].append({
            "query": query, "retrieved_top5": kw_retrieved[:5], **kw_metrics,
        })

        # 2. TF-IDF retriever
        tfidf_retrieved = tfidf_retriever.retrieve(query)
        tfidf_metrics = compute_all_metrics(tfidf_retrieved, relevant_ids)
        all_metrics["TF-IDF"].append(tfidf_metrics)
        per_query_results["TF-IDF"].append({
            "query": query, "retrieved_top5": tfidf_retrieved[:5], **tfidf_metrics,
        })

        # 3. BM25 retriever
        bm25_retrieved = bm25_retriever.retrieve(query)
        bm25_metrics = compute_all_metrics(bm25_retrieved, relevant_ids)
        all_metrics["BM25"].append(bm25_metrics)
        per_query_results["BM25"].append({
            "query": query, "retrieved_top5": bm25_retrieved[:5], **bm25_metrics,
        })

        # 4. SVD Embedding retriever
        embed_retrieved = embed_retriever.retrieve(query)
        embed_metrics = compute_all_metrics(embed_retrieved, relevant_ids)
        all_metrics["SVD Embed"].append(embed_metrics)
        per_query_results["SVD Embed"].append({
            "query": query, "retrieved_top5": embed_retrieved[:5], **embed_metrics,
        })

        if verbose:
            for name in ["Keyword", "TF-IDF", "BM25", "SVD Embed"]:
                m = all_metrics[name][-1]
                top5 = per_query_results[name][-1]["retrieved_top5"]
                print(f"      {name:12s} top-5: {top5}  "
                      f"RR={m['reciprocal_rank']:.3f} "
                      f"R@1={m['recall@1']:.3f} "
                      f"R@3={m['recall@3']:.3f} "
                      f"nDCG@5={m['ndcg@5']:.3f}")

        # 5 & 6. Gemini retrievers (optional)
        if not skip_gemini:
            try:
                gm_retrieved = await gemini_retrieve(query, MOCK_HOME_TAGS)
                gm_metrics = compute_all_metrics(gm_retrieved, relevant_ids)
                all_metrics["Gemini Ranker"].append(gm_metrics)
                per_query_results["Gemini Ranker"].append({
                    "query": query, "retrieved_top5": gm_retrieved[:5], **gm_metrics,
                })
                if verbose:
                    print(f"      {'Gemini Ranker':12s} top-5: {gm_retrieved[:5]}  "
                          f"RR={gm_metrics['reciprocal_rank']:.3f}")
            except Exception as e:
                print(f"      [WARN] Gemini ranker failed: {e}")
                all_metrics["Gemini Ranker"].append(compute_all_metrics([], relevant_ids))

            try:
                answer, e2e_referenced = await gemini_answer_and_extract_tags(
                    query, MOCK_HOME_TAGS
                )
                e2e_metrics = compute_all_metrics(e2e_referenced, relevant_ids)
                all_metrics["Gemini E2E"].append(e2e_metrics)
                per_query_results["Gemini E2E"].append({
                    "query": query,
                    "answer": answer[:200],
                    "referenced_tags": e2e_referenced,
                    **e2e_metrics,
                })
                if verbose:
                    print(f"      {'Gemini E2E':12s} referenced: {e2e_referenced}  "
                          f"RR={e2e_metrics['reciprocal_rank']:.3f}")
            except Exception as e:
                print(f"      [WARN] Gemini E2E failed: {e}")
                all_metrics["Gemini E2E"].append(compute_all_metrics([], relevant_ids))

            await asyncio.sleep(0.5)

    # ---- Aggregate results ----
    aggregated = {}
    for name in retriever_names:
        if all_metrics[name]:
            aggregated[name] = aggregate_metrics(all_metrics[name])
            results[name.lower().replace(" ", "_")] = {
                "per_query": per_query_results.get(name, []),
                "aggregate": aggregated[name],
            }

    # ---- Print results table ----
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

    active_retrievers = [(name, aggregated[name]) for name in retriever_names if name in aggregated]
    headers = ["Metric"] + [name for name, _ in active_retrievers]
    rows = []
    for display_name, key in metrics_to_show:
        row = [display_name]
        for _, agg in active_retrievers:
            row.append(agg.get(key, 0.0))
        rows.append(row)

    print_table(headers, rows, col_width=14)

    # ---- Category breakdown ----
    print("\n" + "=" * 70)
    print("  RESULTS BY CATEGORY (MRR / Recall@3 / nDCG@5)")
    print("=" * 70)

    categories = sorted(set(gt["category"] for gt in GROUND_TRUTH_QUERIES))
    for cat in categories:
        cat_indices = [i for i, gt in enumerate(GROUND_TRUTH_QUERIES) if gt["category"] == cat]
        print(f"\n  {cat} ({len(cat_indices)} queries):")

        for name in retriever_names:
            if name not in aggregated:
                continue
            cat_metrics = [all_metrics[name][i] for i in cat_indices]
            cat_agg = aggregate_metrics(cat_metrics)
            print(f"    {name:14s} — MRR: {cat_agg.get('MRR', 0):.3f}  "
                  f"R@3: {cat_agg.get('mean_recall@3', 0):.3f}  "
                  f"nDCG@5: {cat_agg.get('mean_ndcg@5', 0):.3f}")

    # ---- Implementation details summary ----
    print("\n" + "=" * 70)
    print("  IMPLEMENTATION DETAILS")
    print("=" * 70)
    print(f"  TF-IDF: {tfidf_retriever.vectorizer.vocab_size}-dimensional sparse vectors, "
          f"L2-normalized, cosine similarity ranking")
    print(f"  BM25: Okapi BM25 (k1=1.5, b=0.75), "
          f"log-weighted IDF, length-normalized TF")
    print(f"  SVD Embed: {embed_retriever.embedder.embedding_dim}-dim dense vectors "
          f"from PPMI co-occurrence matrix, power iteration SVD, "
          f"bag-of-embeddings averaging, L2-normalized, cosine similarity")
    print(f"  Keyword: simple word overlap with stopword removal")
    if not skip_gemini:
        print(f"  Gemini Ranker: LLM-based reranking (gemini-2.0-flash)")
        print(f"  Gemini E2E: full RAG pipeline (context + generation + tag extraction)")

    # ---- Save results ----
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "eval_results.json"
    )
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to: {output_path}")

    return results


def main():
    parser = argparse.ArgumentParser(description="MemoryMap RAG Evaluation")
    parser.add_argument("--skip-gemini", action="store_true",
                        help="Skip Gemini-based retrievers (custom only, no API cost)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show per-query details")
    args = parser.parse_args()

    asyncio.run(run_evaluation(skip_gemini=args.skip_gemini, verbose=args.verbose))


if __name__ == "__main__":
    main()
