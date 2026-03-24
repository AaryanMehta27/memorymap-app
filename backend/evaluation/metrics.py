"""
Retrieval evaluation metrics for MemoryMap RAG pipeline.

Computes standard IR metrics:
  - Recall@K (K=1, 5, 10)
  - Mean Reciprocal Rank (MRR)
  - Mean Average Precision (MAP)
  - Normalized Discounted Cumulative Gain (nDCG@K)
  - Hit Rate @K
  - Precision@K
"""

import math
from typing import Optional


def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """
    Recall@K: fraction of relevant items found in the top-K retrieved results.

    recall@k = |relevant ∩ retrieved[:k]| / |relevant|

    Args:
        retrieved_ids: ordered list of tag IDs returned by the system
        relevant_ids: ground truth relevant tag IDs
        k: cutoff rank

    Returns:
        float in [0.0, 1.0]
    """
    if not relevant_ids:
        return 0.0
    top_k = set(retrieved_ids[:k])
    relevant = set(relevant_ids)
    return len(top_k & relevant) / len(relevant)


def precision_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """
    Precision@K: fraction of top-K results that are relevant.

    precision@k = |relevant ∩ retrieved[:k]| / k

    Args:
        retrieved_ids: ordered list of tag IDs returned by the system
        relevant_ids: ground truth relevant tag IDs
        k: cutoff rank

    Returns:
        float in [0.0, 1.0]
    """
    if k == 0:
        return 0.0
    top_k = set(retrieved_ids[:k])
    relevant = set(relevant_ids)
    return len(top_k & relevant) / k


def reciprocal_rank(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    """
    Reciprocal Rank: 1 / rank of the first relevant result.

    RR = 1 / rank_of_first_relevant

    Args:
        retrieved_ids: ordered list of tag IDs returned
        relevant_ids: ground truth relevant tag IDs

    Returns:
        float in [0.0, 1.0] — 0.0 if no relevant result found
    """
    relevant = set(relevant_ids)
    for i, tag_id in enumerate(retrieved_ids):
        if tag_id in relevant:
            return 1.0 / (i + 1)
    return 0.0


def average_precision(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    """
    Average Precision: average of precision@k for each k where a relevant doc is found.

    AP = (1/|relevant|) * Σ precision@k * rel(k)

    Args:
        retrieved_ids: ordered list of tag IDs returned
        relevant_ids: ground truth relevant tag IDs

    Returns:
        float in [0.0, 1.0]
    """
    if not relevant_ids:
        return 0.0

    relevant = set(relevant_ids)
    hits = 0
    sum_precision = 0.0

    for i, tag_id in enumerate(retrieved_ids):
        if tag_id in relevant:
            hits += 1
            sum_precision += hits / (i + 1)

    return sum_precision / len(relevant)


def dcg_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """
    Discounted Cumulative Gain at K.

    DCG@k = Σ(i=1 to k) rel(i) / log2(i + 1)

    Uses binary relevance: 1 if relevant, 0 otherwise.
    """
    relevant = set(relevant_ids)
    dcg = 0.0
    for i, tag_id in enumerate(retrieved_ids[:k]):
        if tag_id in relevant:
            dcg += 1.0 / math.log2(i + 2)  # i+2 because i is 0-indexed
    return dcg


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """
    Normalized Discounted Cumulative Gain at K.

    nDCG@k = DCG@k / IDCG@k

    IDCG is the ideal DCG — all relevant docs at the top.

    Args:
        retrieved_ids: ordered list of tag IDs returned
        relevant_ids: ground truth relevant tag IDs
        k: cutoff rank

    Returns:
        float in [0.0, 1.0]
    """
    actual_dcg = dcg_at_k(retrieved_ids, relevant_ids, k)

    # IDCG: best possible DCG if all relevant docs ranked at top
    ideal_k = min(k, len(relevant_ids))
    ideal_dcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_k))

    if ideal_dcg == 0:
        return 0.0
    return actual_dcg / ideal_dcg


def hit_rate_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int) -> float:
    """
    Hit Rate@K: 1 if any relevant document appears in top-K, else 0.

    Args:
        retrieved_ids: ordered list of tag IDs returned
        relevant_ids: ground truth relevant tag IDs
        k: cutoff rank

    Returns:
        1.0 or 0.0
    """
    top_k = set(retrieved_ids[:k])
    relevant = set(relevant_ids)
    return 1.0 if top_k & relevant else 0.0


def compute_all_metrics(
    retrieved_ids: list[str],
    relevant_ids: list[str],
    k_values: Optional[list[int]] = None,
) -> dict:
    """
    Compute all retrieval metrics for a single query.

    Args:
        retrieved_ids: ordered list of tag IDs returned by system
        relevant_ids: ground truth relevant tag IDs
        k_values: list of K cutoffs (default: [1, 3, 5, 10])

    Returns:
        dict with all metric values
    """
    if k_values is None:
        k_values = [1, 3, 5, 10]

    results = {
        "reciprocal_rank": reciprocal_rank(retrieved_ids, relevant_ids),
        "average_precision": average_precision(retrieved_ids, relevant_ids),
    }

    for k in k_values:
        results[f"recall@{k}"] = recall_at_k(retrieved_ids, relevant_ids, k)
        results[f"precision@{k}"] = precision_at_k(retrieved_ids, relevant_ids, k)
        results[f"ndcg@{k}"] = ndcg_at_k(retrieved_ids, relevant_ids, k)
        results[f"hit_rate@{k}"] = hit_rate_at_k(retrieved_ids, relevant_ids, k)

    return results


def aggregate_metrics(all_query_results: list[dict]) -> dict:
    """
    Aggregate metrics across all queries (macro-averaging).

    Args:
        all_query_results: list of dicts from compute_all_metrics()

    Returns:
        dict with mean value for each metric
    """
    if not all_query_results:
        return {}

    keys = all_query_results[0].keys()
    aggregated = {}

    for key in keys:
        values = [r[key] for r in all_query_results]
        aggregated[f"mean_{key}"] = sum(values) / len(values)

    # Also add MRR explicitly (it's the mean of reciprocal ranks)
    aggregated["MRR"] = aggregated.get("mean_reciprocal_rank", 0.0)
    # MAP is mean of average precisions
    aggregated["MAP"] = aggregated.get("mean_average_precision", 0.0)

    return aggregated
