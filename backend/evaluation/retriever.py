"""
Retriever module for MemoryMap RAG evaluation.

Implements tag retrieval strategies that simulate what query.py does:
1. Keyword matching (baseline)
2. Gemini-powered semantic matching (production approach)
3. Embedding-based hybrid retrieval (TF-IDF + BM25, from embeddings.py)

The retriever takes a patient question and a list of available tags,
and returns an ordered list of the most relevant tags.
"""

import asyncio
import os
import re
from dotenv import load_dotenv

load_dotenv()


def build_context_from_tags(tags: list[dict]) -> str:
    """Format tags into the compact context string used for Gemini queries."""
    lines = []
    for tag in tags:
        lines.append(
            f"Room: {tag['room_name']} | Object: {tag['label']} | "
            f"Position: {tag['position']} | Notes: {tag.get('notes', '')}"
        )
    return "\n".join(lines)


def keyword_retrieve(question: str, tags: list[dict]) -> list[str]:
    """
    Baseline retriever: simple keyword matching.
    Scores each tag by how many question words appear in its label + notes.
    Returns tag IDs ordered by score (descending).
    """
    # Normalize question
    q_words = set(re.findall(r"\w+", question.lower()))
    # Remove stop words
    stop = {"where", "is", "my", "the", "are", "did", "i", "put", "find", "can",
            "a", "an", "to", "do", "we", "keep", "need", "want", "some", "it",
            "in", "on", "of", "for", "up", "have", "has"}
    q_words -= stop

    scored = []
    for tag in tags:
        text = f"{tag['label']} {tag.get('notes', '')} {tag['room_name']}".lower()
        text_words = set(re.findall(r"\w+", text))
        overlap = len(q_words & text_words)
        scored.append((tag["id"], overlap))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [tag_id for tag_id, _ in scored]


async def gemini_retrieve(question: str, tags: list[dict]) -> list[str]:
    """
    Production retriever: uses Gemini to rank tags by relevance.
    Sends the full tag context + question, asks Gemini to return ordered tag IDs.
    """
    from services.gemini_client import _get_client, TEXT_MODEL
    from google.genai import types

    context = build_context_from_tags(tags)
    tag_id_list = ", ".join(t["id"] for t in tags)

    system = (
        "You are a retrieval ranking system. Given a patient's question and a list of "
        "tagged objects in their home, rank the tags from most to least relevant. "
        "Return ONLY a JSON array of tag IDs in order of relevance. "
        "Include ALL tag IDs, even if barely relevant."
    )

    prompt = (
        f"Home layout data:\n{context}\n\n"
        f"Available tag IDs: {tag_id_list}\n\n"
        f"Patient's question: {question}\n\n"
        f'Return ONLY a JSON array of tag IDs ranked by relevance, e.g. ["tag-001", "tag-003", ...]'
    )

    import json

    def _call():
        return _get_client().models.generate_content(
            model=TEXT_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=system),
        )

    response = await asyncio.to_thread(_call)
    text = response.text.strip()

    # Strip markdown fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        ranked_ids = json.loads(text)
        if isinstance(ranked_ids, list):
            return ranked_ids
    except json.JSONDecodeError:
        pass

    # Fallback: try to extract IDs from the response
    found_ids = re.findall(r"tag-\d+", text)
    return found_ids if found_ids else [t["id"] for t in tags]


async def gemini_answer_and_extract_tags(
    question: str, tags: list[dict]
) -> tuple[str, list[str]]:
    """
    End-to-end RAG: ask Gemini the question with context, then extract
    which tags were referenced in the answer (simulates query.py behavior).
    Returns (answer_text, list_of_referenced_tag_ids).
    """
    from services.gemini_client import query_with_context

    context = build_context_from_tags(tags)
    answer = await query_with_context(context, question)

    # Extract referenced tags by checking if label appears in the answer
    referenced = []
    for tag in tags:
        if tag["label"].lower() in answer.lower():
            referenced.append(tag["id"])

    return answer, referenced


# ===========================================================================
#  Embedding-based Hybrid Retriever (wraps embeddings.py HybridRetriever)
# ===========================================================================

class EmbeddingRetriever:
    """
    Retriever that uses the custom HybridRetriever from embeddings.py.

    This wraps the hand-crafted TF-IDF + BM25 hybrid system so it can
    be evaluated alongside the keyword and Gemini retrievers in the
    evaluation pipeline.

    The interface matches keyword_retrieve() — takes a question and tags,
    returns an ordered list of tag IDs.
    """

    def __init__(self, tfidf_weight: float = 0.4, bm25_weight: float = 0.6):
        self.tfidf_weight = tfidf_weight
        self.bm25_weight = bm25_weight
        self._tag_retriever = None

    def fit(self, tags: list[dict]) -> "EmbeddingRetriever":
        """Build the hybrid index on the provided tags."""
        from evaluation.embeddings import TagRetriever

        self._tag_retriever = TagRetriever(tags)
        # Override weights if non-default
        self._tag_retriever.retriever.tfidf_weight = self.tfidf_weight
        self._tag_retriever.retriever.bm25_weight = self.bm25_weight
        return self

    def retrieve(self, question: str, tags: list[dict]) -> list[str]:
        """
        Retrieve ranked tag IDs for a patient question.

        If fit() has not been called yet, it will be called automatically
        with the provided tags (lazy initialization).

        Args:
            question: patient's natural language question
            tags: list of tag dicts (used for lazy init if needed)

        Returns:
            List of tag ID strings, ordered by relevance (best first).
        """
        if self._tag_retriever is None:
            self.fit(tags)
        return self._tag_retriever.find_relevant_tag_ids(question, top_k=len(tags))

    def explain(self, question: str) -> str:
        """Get human-readable explanation of retrieval. Must call fit() first."""
        if self._tag_retriever is None:
            raise RuntimeError("Call fit() before explain()")
        return self._tag_retriever.explain(question)
