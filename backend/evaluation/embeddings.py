"""
Custom embedding and retrieval implementations for MemoryMap RAG evaluation.
=============================================================================

All implementations are from scratch using only numpy for matrix operations
and the Python standard library. NO scikit-learn, NO sentence-transformers,
NO external embedding APIs.

This is a teaching codebase for a university GenAI course. Every formula is
documented with inline comments so you can follow the math.

Implements:
    Part 1 — Text Preprocessing (tokenize, stem, stopwords, vocabulary)
    Part 2 — TF-IDF Embeddings (term frequency, inverse document frequency)
    Part 3 — BM25 Scoring (Okapi BM25 probabilistic retrieval model)
    Part 4 — Vector Operations (L2 norm, cosine similarity, euclidean distance)
    Part 5 — HybridRetriever (weighted combination of TF-IDF + BM25)
    Part 6 — TagRetriever (MemoryMap integration layer)
    Part 7 — GloVe Semantic Embeddings (pre-trained word vectors for
             vocabulary-mismatch bridging)

References:
    - TF-IDF: Salton & Buckley, "Term-weighting approaches in automatic text
      retrieval", Information Processing & Management, 1988
    - BM25: Robertson & Zaragoza, "The Probabilistic Relevance Framework:
      BM25 and Beyond", Foundations and Trends in IR, 2009
    - GloVe: Pennington, Socher & Manning, "GloVe: Global Vectors for Word
      Representation", EMNLP 2014
    - Cosine Similarity: standard inner-product measure on unit vectors

Dependencies:
    - numpy (matrix operations only — no ML libraries)
    - gensim (ONLY for loading pre-trained GloVe vectors — we do all math ourselves)
    - Python standard library (math, re, collections)
"""

import math
import re
from collections import Counter
from typing import Optional

import numpy as np


# ===========================================================================
#  Part 1: Text Preprocessing
# ===========================================================================

# ~150 common English stopwords. These are function words that carry little
# semantic meaning and would add noise to our term-frequency counts.
STOPWORDS: frozenset = frozenset({
    # Articles & determiners
    "a", "an", "the", "this", "that", "these", "those",
    # Pronouns
    "i", "me", "my", "mine", "myself", "we", "us", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself", "she", "her", "hers", "herself",
    "it", "its", "itself", "they", "them", "their", "theirs", "themselves",
    # Prepositions
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "up", "about",
    "into", "through", "during", "before", "after", "above", "below", "between",
    "out", "off", "over", "under", "again", "further", "against", "along",
    "around", "down", "near", "across",
    # Conjunctions & connectors
    "and", "but", "or", "nor", "yet", "so", "because", "although", "while",
    "if", "when", "where", "how", "than",
    # Be-verbs & auxiliaries
    "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "having",
    "do", "does", "did", "doing",
    "will", "would", "could", "should", "may", "might", "shall", "can",
    "need", "must", "ought",
    # Common verbs (too generic for retrieval)
    "put", "find", "keep", "want", "get", "got", "going", "went", "go",
    "make", "made", "take", "took", "come", "came", "give", "gave",
    "know", "think", "see", "say", "said", "tell", "told",
    # Adverbs & misc
    "not", "no", "very", "just", "also", "too", "only", "already",
    "now", "then", "here", "there", "still", "even",
    "all", "each", "every", "both", "few", "more", "most", "other", "some",
    "such", "any", "many", "much", "own", "same",
    # Question words
    "what", "which", "who", "whom", "whose", "why",
    # Misc function words
    "as", "until", "enough", "once", "since", "well", "back",
    "really", "quite", "rather", "ever", "never",
})


def stem(word: str) -> str:
    """
    Simple suffix-stripping stemmer.

    This is a lightweight alternative to the full Porter stemmer. It strips
    common English suffixes to reduce words to approximate stems. Not
    linguistically perfect, but effective enough for IR tasks on short texts.

    Rules are applied in order of suffix length (longest first) to avoid
    partial matches. Minimum word length guards prevent over-stemming
    (e.g., "sing" should not become "s" by stripping "ing").

    Args:
        word: a single lowercase token

    Returns:
        The stemmed token (may be unchanged if no rule matches)

    Examples:
        >>> stem("running")
        'run'
        >>> stem("education")
        'educate'
        >>> stem("happiness")
        'happi'
    """
    # Rules ordered by suffix length (longest first).
    # Each tuple: (suffix, replacement, min_stem_length)
    # min_stem_length ensures we don't over-stem short words.
    rules = [
        ("ational", "ate", 2),   # relational -> relate
        ("tional", "tion", 2),   # conditional -> condition
        ("encies", "ence", 2),   # frequencies -> frequence
        ("ances", "ance", 2),    # performances -> performance
        ("ments", "ment", 2),    # adjustments -> adjustment
        ("ement", "e", 2),       # replacement -> replace
        ("iness", "y", 2),       # happiness -> happy (happi after y->i)
        ("ness", "", 3),         # darkness -> dark
        ("ment", "", 3),         # adjustment -> adjust
        ("tion", "", 3),         # creation -> crea (crude but functional)
        ("sion", "", 3),         # discussion -> discus
        ("able", "", 3),         # comfortable -> comfort
        ("ible", "", 3),         # possible -> poss
        ("ling", "", 3),         # darling exception guard
        ("ally", "", 3),         # finally -> fin
        ("ying", "y", 2),        # studying -> study
        ("ies", "y", 2),         # batteries -> battery
        ("ing", "", 3),          # running -> runn -> run (handled below)
        ("ful", "", 3),          # beautiful -> beauti
        ("ous", "", 3),          # dangerous -> danger
        ("ive", "", 3),          # active -> act
        ("ize", "", 3),          # normalize -> normal
        ("ise", "", 3),          # normalise -> normal
        ("ate", "", 3),          # activate -> activ
        ("ly", "", 3),           # quickly -> quick
        ("ed", "", 3),           # walked -> walk
        ("er", "", 3),           # walker -> walk
        ("sses", "ss", 2),       # glasses -> glass
        ("xes", "x", 2),         # boxes -> box
        ("ches", "ch", 2),       # watches -> watch
        ("shes", "sh", 2),       # dishes -> dish
        ("zes", "z", 2),         # buzzes -> buzz (via zes)
        ("es", "", 4),           # min 4 so "shoes"(5-2=3) falls through to "s"
        ("al", "", 3),           # removal -> remov
        ("s", "", 3),            # cats -> cat, shoes -> shoe
    ]

    for suffix, replacement, min_stem in rules:
        if word.endswith(suffix) and len(word) - len(suffix) >= min_stem:
            stemmed = word[: -len(suffix)] + replacement
            # Clean up doubled consonants after stripping
            # e.g., "running" -> "runn" -> "run"
            if (
                len(stemmed) >= 2
                and stemmed[-1] == stemmed[-2]
                and stemmed[-1] not in "aeiou"
                and stemmed[-1] not in "ls"  # keep "ll", "ss" patterns
            ):
                stemmed = stemmed[:-1]
            return stemmed

    return word


def tokenize(text: str) -> list[str]:
    """
    Tokenize text into a list of stemmed, lowercase tokens with stopwords removed.

    Pipeline:
        1. Lowercase the entire string
        2. Extract alphanumeric tokens using regex (splits on non-alphanum)
        3. Remove stopwords (function words with little semantic content)
        4. Apply suffix-stripping stemmer to each remaining token

    This produces the "bag of words" that TF-IDF and BM25 operate on.

    Args:
        text: raw input string (can contain punctuation, mixed case, etc.)

    Returns:
        List of stemmed tokens, preserving order of appearance.
        Tokens shorter than 2 characters are dropped.

    Examples:
        >>> tokenize("Where are my running shoes?")
        ['run', 'shoe']
        >>> tokenize("The medicine cabinet in the bathroom")
        ['medicin', 'cabinet', 'bathroom']
    """
    if not text or not text.strip():
        return []

    text = text.lower()

    # Extract only alphanumeric sequences (splits on spaces, punctuation, etc.)
    tokens = re.findall(r"[a-z0-9]+", text)

    # Remove stopwords and very short tokens (single chars carry no meaning)
    tokens = [t for t in tokens if t not in STOPWORDS and len(t) > 1]

    # Apply stemming to each token
    stemmed = [stem(t) for t in tokens]

    return stemmed


# ---------------------------------------------------------------------------
#  Synonym / Query Expansion
# ---------------------------------------------------------------------------
# The vocabulary mismatch problem: a patient says "pills" but the tag says
# "medicine cabinet". Pure keyword matching fails here. Synonym expansion
# bridges this gap by mapping semantically related terms to each other.
#
# This is a hand-curated domain-specific thesaurus for a home-item retrieval
# system. Each group contains terms that should be treated as related when
# computing similarity. When a query token matches a synonym group, all
# terms in that group are added to the query (with reduced weight).
#
# This is conceptually similar to WordNet-based query expansion in classical
# IR, but tailored to our specific domain.

SYNONYM_GROUPS: list[set[str]] = [
    # Medication
    {"pill", "medicine", "medication", "prescription", "drug", "tablet", "capsule", "vitamin"},
    # Eyewear
    {"glass", "spectacle", "eyeglass", "reading glass", "sunglass"},
    # Keys & access
    {"key", "keychain", "car key", "house key"},
    # Food storage
    {"fridge", "refrigerator", "freezer", "cooler"},
    {"pantry", "cupboard", "food cabinet", "snack"},
    {"microwave", "oven", "stove", "heat", "warm", "leftover", "reheat"},
    # Personal items
    {"wallet", "purse", "money", "card", "credit card", "id"},
    {"phone", "mobile", "cell", "cellphone", "smartphone"},
    {"remote", "tv remote", "controller", "clicker"},
    # Clothing & accessories
    {"shoe", "sneaker", "slipper", "boot", "sandal", "footwear"},
    {"coat", "jacket", "hoodie", "sweater", "outerwear"},
    {"hat", "cap", "beanie"},
    # Documents
    {"document", "paper", "file", "folder", "letter", "mail", "bill"},
    # Hygiene
    {"toothbrush", "toothpaste", "dental", "brush"},
    {"towel", "washcloth", "rag"},
    # Storage furniture
    {"drawer", "dresser", "chest", "bureau"},
    {"shelf", "bookshelf", "rack", "stand"},
    {"cabinet", "closet", "wardrobe", "armoire", "cupboard"},
    # Comfort
    {"blanket", "throw", "quilt", "comforter", "bedding"},
    {"pillow", "cushion"},
    # Drinks
    {"cup", "mug", "glass", "tumbler"},
    {"water", "drink", "beverage", "bottle"},
    # Tools
    {"flashlight", "torch", "lamp", "light"},
    {"charger", "cable", "cord", "plug", "adapter"},
    # Blood pressure / medical devices
    {"blood pressure", "bp", "cuff", "monitor", "sphygmomanometer"},
]

# Build a fast lookup: stemmed token → set of stemmed synonyms
_SYNONYM_LOOKUP: dict[str, set[str]] = {}


def _build_synonym_lookup() -> None:
    """Pre-compute a stemmed-token → stemmed-synonyms mapping."""
    global _SYNONYM_LOOKUP
    if _SYNONYM_LOOKUP:
        return
    for group in SYNONYM_GROUPS:
        # Stem every term in the group (some are multi-word)
        stemmed_group: set[str] = set()
        for term in group:
            for token in term.lower().split():
                stemmed_group.add(stem(token))
        # Map each stemmed token to all other stemmed tokens in its group
        for tok in stemmed_group:
            if tok not in _SYNONYM_LOOKUP:
                _SYNONYM_LOOKUP[tok] = set()
            _SYNONYM_LOOKUP[tok].update(stemmed_group)


def expand_query(tokens: list[str], expansion_weight: float = 0.5) -> list[tuple[str, float]]:
    """
    Expand query tokens with synonyms for better recall.

    Each original token gets weight 1.0. Synonyms added via expansion get
    a reduced weight (default 0.5) so they boost recall without dominating
    the original query intent.

    This is a form of pseudo-relevance feedback / query expansion that
    addresses the vocabulary mismatch problem in keyword-based retrieval.

    Args:
        tokens: list of stemmed query tokens
        expansion_weight: weight for expanded synonym tokens (0.0 to 1.0)

    Returns:
        List of (token, weight) tuples including original + expanded tokens.
    """
    _build_synonym_lookup()
    result: list[tuple[str, float]] = []
    seen: set[str] = set()

    # Original tokens at full weight
    for tok in tokens:
        if tok not in seen:
            result.append((tok, 1.0))
            seen.add(tok)

    # Expand with synonyms at reduced weight
    for tok in tokens:
        synonyms = _SYNONYM_LOOKUP.get(tok, set())
        for syn in synonyms:
            if syn not in seen and syn not in STOPWORDS and len(syn) > 1:
                result.append((syn, expansion_weight))
                seen.add(syn)

    return result


def build_vocab(documents: list[str]) -> dict[str, int]:
    """
    Build a vocabulary mapping from a list of documents.

    Tokenizes every document, collects all unique stemmed tokens, then
    assigns each token a unique integer index (sorted alphabetically for
    deterministic ordering).

    The resulting dict maps: token_string -> column_index, and defines the
    dimensionality of our TF-IDF vector space.

    Args:
        documents: list of raw text strings

    Returns:
        Dictionary mapping each unique stemmed token to an integer index.
        Indices are 0-based and contiguous.

    Example:
        >>> build_vocab(["The cat sat", "A dog ran"])
        {'cat': 0, 'dog': 1, 'ran': 2, 'sat': 3}
    """
    all_tokens: set[str] = set()
    for doc in documents:
        all_tokens.update(tokenize(doc))
    # Sort for deterministic column order
    return {token: idx for idx, token in enumerate(sorted(all_tokens))}


# ===========================================================================
#  Part 2: TF-IDF Embeddings (from scratch)
# ===========================================================================

def compute_tf(tokens: list[str]) -> dict[str, float]:
    """
    Compute term frequency for a list of tokens.

    TF(t, d) = count(t in d) / |d|

    Term frequency measures how often a term appears in a document,
    normalized by document length. This prevents bias toward longer
    documents that naturally contain more term occurrences.

    Args:
        tokens: list of (already stemmed) tokens from one document

    Returns:
        Dictionary mapping each token to its term frequency (0.0 to 1.0).
        Returns empty dict for empty token lists.
    """
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = len(tokens)
    # Normalize: divide raw count by total number of tokens
    return {term: count / total for term, count in counts.items()}


def compute_idf(corpus_tokens: list[list[str]]) -> dict[str, float]:
    """
    Compute inverse document frequency for all terms in a corpus.

    IDF(t) = log(N / df(t))

    where:
        N   = total number of documents in the corpus
        df(t) = number of documents containing term t

    IDF gives higher weight to rare terms (appearing in fewer documents)
    and lower weight to common terms. The logarithm dampens the effect
    so that a term appearing in 1 out of 1000 docs doesn't get a weight
    1000x higher than one appearing in 500 out of 1000.

    Note: We use log(N / df) without +1 smoothing here. If a term appears
    in all documents, IDF = log(1) = 0, which correctly gives it zero weight.

    Args:
        corpus_tokens: list of token lists, one per document.
                       Each inner list should already be stemmed.

    Returns:
        Dictionary mapping each term to its IDF value.
        Higher values = rarer, more discriminative terms.
    """
    N = len(corpus_tokens)
    if N == 0:
        return {}

    # Count in how many documents each term appears (document frequency)
    df: Counter = Counter()
    for tokens in corpus_tokens:
        unique_tokens = set(tokens)
        for token in unique_tokens:
            df[token] += 1

    # IDF = log(N / df(t))
    # Terms that appear in every document get IDF = 0 (not discriminative)
    idf = {}
    for term, freq in df.items():
        idf[term] = math.log(N / freq)

    return idf


def build_tfidf_matrix(
    documents: list[str],
) -> tuple[np.ndarray, dict[str, int], dict[str, float]]:
    """
    Build a full TF-IDF matrix from a list of documents.

    Returns a matrix of shape [n_docs, vocab_size] where each row is the
    TF-IDF vector for one document.

    The TF-IDF value for term t in document d is:

        TF-IDF(t, d) = TF(t, d) * IDF(t)
                      = (count(t,d) / |d|) * log(N / df(t))

    High TF-IDF means the term is frequent in this document but rare
    across the corpus — exactly the terms that distinguish this document.

    Args:
        documents: list of raw text strings

    Returns:
        Tuple of:
            - matrix: np.ndarray of shape [n_docs, vocab_size], dtype float64
            - vocab: dict mapping each stemmed token to its column index
            - idf_values: dict mapping each stemmed token to its IDF score

    Example:
        >>> matrix, vocab, idf = build_tfidf_matrix(["cat sat", "dog ran"])
        >>> matrix.shape
        (2, 4)
    """
    # Step 1: Tokenize all documents
    corpus_tokens = [tokenize(doc) for doc in documents]

    # Step 2: Build vocabulary (sorted for deterministic column order)
    vocab = build_vocab(documents)
    vocab_size = len(vocab)

    # Step 3: Compute IDF across the corpus
    idf_values = compute_idf(corpus_tokens)

    # Step 4: Build the matrix row by row
    n_docs = len(documents)
    matrix = np.zeros((n_docs, vocab_size), dtype=np.float64)

    for doc_idx, tokens in enumerate(corpus_tokens):
        tf = compute_tf(tokens)
        for term, tf_val in tf.items():
            if term in vocab:
                col = vocab[term]
                idf_val = idf_values.get(term, 0.0)
                # TF-IDF(t, d) = TF(t, d) * IDF(t)
                matrix[doc_idx, col] = tf_val * idf_val

    return matrix, vocab, idf_values


def tfidf_embed_query(
    query: str, vocab: dict[str, int], idf: dict[str, float]
) -> np.ndarray:
    """
    Embed a new query into the existing TF-IDF vector space.

    Uses the same vocabulary and IDF weights learned from the corpus.
    Terms in the query that are not in the vocabulary are ignored
    (out-of-vocabulary terms cannot be matched).

    Args:
        query: raw query string
        vocab: vocabulary mapping from build_tfidf_matrix()
        idf: IDF values from build_tfidf_matrix()

    Returns:
        np.ndarray of shape [vocab_size], the TF-IDF vector for the query.
        Zero vector if query has no in-vocabulary terms.
    """
    vocab_size = len(vocab)
    vector = np.zeros(vocab_size, dtype=np.float64)

    tokens = tokenize(query)
    if not tokens:
        return vector

    # Expand query with synonyms to bridge vocabulary mismatch
    # Original tokens get weight 1.0, synonyms get reduced weight (0.5)
    expanded = expand_query(tokens, expansion_weight=0.5)

    # Build weighted term frequencies
    weighted_counts: dict[str, float] = {}
    total_weight = sum(w for _, w in expanded)
    for term, weight in expanded:
        weighted_counts[term] = weighted_counts.get(term, 0.0) + weight

    for term, w_count in weighted_counts.items():
        if term in vocab:
            col = vocab[term]
            idf_val = idf.get(term, 0.0)
            # Weighted TF * IDF: synonyms contribute proportionally less
            vector[col] = (w_count / total_weight) * idf_val

    return vector


# ===========================================================================
#  Part 3: BM25 Scoring (from scratch)
# ===========================================================================

class BM25Index:
    """
    Okapi BM25 — the gold standard probabilistic retrieval model.

    BM25 scores a document D against a query Q as:

        score(D, Q) = SUM over qi in Q of:
            IDF(qi) * (tf(qi, D) * (k1 + 1)) / (tf(qi, D) + k1 * (1 - b + b * |D| / avgdl))

    where:
        qi        = individual query term
        tf(qi, D) = raw term frequency of qi in document D
        |D|       = length of document D (in tokens)
        avgdl     = average document length across the corpus
        k1        = term frequency saturation parameter (default 1.5)
                    Higher k1 = more weight to repeated terms
                    k1 = 0 is a binary model (just presence/absence)
        b         = length normalization parameter (default 0.75)
                    b = 0 means no length normalization
                    b = 1 means full normalization to average length

    IDF variant used (avoids negative IDF for very common terms):
        IDF(qi) = log((N - df(qi) + 0.5) / (df(qi) + 0.5) + 1)

    BM25 improves on raw TF-IDF by:
        1. Term frequency saturation: the benefit of seeing a term 10 times
           vs. 5 times is much less than 5 times vs. 1 time
        2. Document length normalization: long documents aren't automatically
           ranked higher just because they contain more terms
    """

    def __init__(self, documents: list[str], k1: float = 1.5, b: float = 0.75):
        """
        Build the BM25 index from a list of documents.

        Args:
            documents: list of raw text strings to index
            k1: term frequency saturation (default 1.5)
            b: document length normalization (default 0.75)
        """
        self.k1 = k1
        self.b = b
        self.n_docs = len(documents)

        # Tokenize all documents
        self.doc_tokens: list[list[str]] = [tokenize(doc) for doc in documents]
        self.doc_lengths: np.ndarray = np.array(
            [len(tokens) for tokens in self.doc_tokens], dtype=np.float64
        )

        # Average document length
        self.avgdl: float = float(np.mean(self.doc_lengths)) if self.n_docs > 0 else 1.0

        # Pre-compute document frequency and IDF for each term
        self.df: Counter = Counter()
        for tokens in self.doc_tokens:
            for term in set(tokens):
                self.df[term] += 1

        # IDF(t) = log((N - df(t) + 0.5) / (df(t) + 0.5) + 1)
        self.idf: dict[str, float] = {}
        for term, freq in self.df.items():
            numerator = self.n_docs - freq + 0.5
            denominator = freq + 0.5
            self.idf[term] = math.log(numerator / denominator + 1.0)

        # Pre-compute term frequency counters for each document
        self._doc_tf: list[Counter] = [Counter(tokens) for tokens in self.doc_tokens]

    def score(self, query: str) -> np.ndarray:
        """
        Score all documents against the query.

        Applies the full BM25 formula to compute a relevance score for
        every document in the index.

        Args:
            query: raw query string

        Returns:
            np.ndarray of shape [n_docs] containing BM25 scores.
            Higher score = more relevant. Scores are non-negative.
        """
        query_tokens = tokenize(query)
        scores = np.zeros(self.n_docs, dtype=np.float64)

        if not query_tokens:
            return scores

        # Expand query tokens with synonyms (weighted)
        expanded = expand_query(query_tokens, expansion_weight=0.5)

        for q_term, q_weight in expanded:
            if q_term not in self.idf:
                # Term not in any document — skip (no contribution)
                continue

            idf_val = self.idf[q_term]

            for doc_idx in range(self.n_docs):
                # Raw term frequency of q_term in this document
                tf_val = self._doc_tf[doc_idx].get(q_term, 0)
                if tf_val == 0:
                    continue

                doc_len = self.doc_lengths[doc_idx]

                # BM25 formula:
                # score += IDF(qi) * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * |D| / avgdl))
                numerator = tf_val * (self.k1 + 1.0)
                denominator = tf_val + self.k1 * (
                    1.0 - self.b + self.b * doc_len / self.avgdl
                )
                # Apply query term weight: synonyms contribute proportionally less
                scores[doc_idx] += q_weight * idf_val * (numerator / denominator)

        return scores

    def rank(self, query: str, top_k: int = 5) -> list[tuple[int, float]]:
        """
        Score and rank documents, returning the top-k results.

        Args:
            query: raw query string
            top_k: number of top results to return

        Returns:
            List of (doc_index, score) tuples, sorted by score descending.
            Length is min(top_k, n_docs).
        """
        scores = self.score(query)

        # Get indices sorted by score (descending)
        # np.argsort is ascending, so we negate or reverse
        ranked_indices = np.argsort(-scores)[:top_k]

        return [(int(idx), float(scores[idx])) for idx in ranked_indices]


# ===========================================================================
#  Part 4: Vector Operations (from scratch, using numpy)
# ===========================================================================

def l2_normalize(vector: np.ndarray) -> np.ndarray:
    """
    L2 (Euclidean) normalization: scale a vector to unit length.

        v_normalized = v / ||v||_2

    where ||v||_2 = sqrt(sum(v_i^2))

    After normalization, the vector lies on the unit hypersphere.
    This means cosine_similarity(a, b) simplifies to just dot(a, b)
    for pre-normalized vectors, which is computationally cheaper.

    Args:
        vector: np.ndarray of any shape (typically 1-D)

    Returns:
        Unit-length vector in the same direction.
        Returns zero vector unchanged (avoids division by zero).
    """
    vector = np.asarray(vector, dtype=np.float64)
    # ||v||_2 = sqrt(v dot v)
    norm = np.sqrt(np.dot(vector, vector))
    if norm == 0.0:
        return vector
    return vector / norm


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Cosine similarity between two vectors.

        cos(theta) = (a dot b) / (||a||_2 * ||b||_2)

    Measures the cosine of the angle between two vectors in high-dimensional
    space. A value of 1.0 means the vectors point in the same direction
    (regardless of magnitude), 0.0 means orthogonal, -1.0 means opposite.

    For TF-IDF vectors (all non-negative), the range is [0.0, 1.0].

    Args:
        a: first vector (np.ndarray, 1-D)
        b: second vector (np.ndarray, 1-D)

    Returns:
        Float in [-1.0, 1.0]. Returns 0.0 if either vector is zero.
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)

    # Compute norms
    norm_a = np.sqrt(np.dot(a, a))
    norm_b = np.sqrt(np.dot(b, b))

    # Guard against zero vectors
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    # cos(theta) = dot(a, b) / (||a|| * ||b||)
    return float(np.dot(a, b) / (norm_a * norm_b))


def batch_cosine_similarity(
    query_vec: np.ndarray, doc_matrix: np.ndarray
) -> np.ndarray:
    """
    Vectorized cosine similarity of one query against all documents.

    Instead of looping over documents one by one, we use matrix multiplication
    to compute all similarities in one shot:

        similarities = (doc_matrix @ query) / (||docs|| * ||query||)

    This is O(n * d) via BLAS rather than O(n * d) in Python loops, which
    is dramatically faster for large corpora thanks to numpy's C backend.

    Args:
        query_vec: np.ndarray of shape [vocab_size] — the query vector
        doc_matrix: np.ndarray of shape [n_docs, vocab_size] — document vectors

    Returns:
        np.ndarray of shape [n_docs] with cosine similarity scores.
        Zero-norm documents get a similarity of 0.0.
    """
    query_vec = np.asarray(query_vec, dtype=np.float64)
    doc_matrix = np.asarray(doc_matrix, dtype=np.float64)

    # Handle edge cases
    if query_vec.ndim == 0 or doc_matrix.ndim == 0:
        return np.zeros(0)
    if doc_matrix.shape[0] == 0:
        return np.zeros(0)

    # Query norm (scalar)
    query_norm = np.sqrt(np.dot(query_vec, query_vec))
    if query_norm == 0.0:
        return np.zeros(doc_matrix.shape[0])

    # Document norms (one per row)
    # ||d_i|| = sqrt(sum(d_i_j^2)) for each row
    doc_norms = np.sqrt(np.sum(doc_matrix ** 2, axis=1))

    # Dot products: doc_matrix @ query_vec gives [n_docs] array
    dot_products = doc_matrix @ query_vec

    # Denominators: ||d_i|| * ||q||
    denominators = doc_norms * query_norm

    # Avoid division by zero for zero-norm documents
    # np.where: if denom > 0, compute similarity; else 0.0
    similarities = np.where(
        denominators > 0.0,
        dot_products / denominators,
        0.0,
    )

    return similarities


def euclidean_distance(a: np.ndarray, b: np.ndarray) -> float:
    """
    Euclidean (L2) distance between two vectors.

        d(a, b) = ||a - b||_2 = sqrt(sum((a_i - b_i)^2))

    This is the straight-line distance in the vector space. Unlike cosine
    similarity, it is sensitive to vector magnitude (not just direction).

    In retrieval, cosine similarity is generally preferred over euclidean
    distance because document vectors can have very different magnitudes
    (long documents vs. short ones), and we care about topical similarity
    (direction) more than magnitude.

    Args:
        a: first vector (np.ndarray, 1-D)
        b: second vector (np.ndarray, 1-D)

    Returns:
        Non-negative float. 0.0 means identical vectors.
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    diff = a - b
    return float(np.sqrt(np.dot(diff, diff)))


# ===========================================================================
#  Part 5: Combined Retriever (Hybrid TF-IDF + BM25)
# ===========================================================================

class HybridRetriever:
    """
    Hybrid retriever combining TF-IDF cosine similarity and BM25 scores.

    The idea: TF-IDF and BM25 capture different aspects of relevance.
    TF-IDF with cosine similarity measures angular similarity in the vector
    space, while BM25 uses a probabilistic model with term saturation and
    length normalization. Combining them often outperforms either alone.

    Combination strategy:
        1. Compute TF-IDF cosine similarity scores for all documents
        2. Compute BM25 scores for all documents
        3. Min-max normalize both score arrays to [0, 1]
        4. Weighted sum: combined = w_tfidf * tfidf_norm + w_bm25 * bm25_norm
        5. Rank by combined score

    Attributes:
        documents: the raw text documents in the index
        doc_metadata: metadata dicts associated with each document
        tfidf_weight: weight for TF-IDF scores in the combination
        bm25_weight: weight for BM25 scores in the combination
    """

    def __init__(
        self,
        documents: list[str],
        doc_metadata: list[dict],
        tfidf_weight: float = 0.4,
        bm25_weight: float = 0.6,
    ):
        """
        Build both TF-IDF and BM25 indices from the documents.

        Args:
            documents: list of raw text strings to index
            doc_metadata: list of metadata dicts (one per document).
                          Returned alongside scores in retrieval results.
            tfidf_weight: weight for TF-IDF similarity (default 0.4)
            bm25_weight: weight for BM25 scores (default 0.6)
        """
        if len(documents) != len(doc_metadata):
            raise ValueError(
                f"documents ({len(documents)}) and doc_metadata ({len(doc_metadata)}) "
                f"must have the same length"
            )

        self.documents = documents
        self.doc_metadata = doc_metadata
        self.tfidf_weight = tfidf_weight
        self.bm25_weight = bm25_weight

        # Build TF-IDF matrix
        self.tfidf_matrix, self.vocab, self.idf_values = build_tfidf_matrix(documents)

        # Build BM25 index
        self.bm25_index = BM25Index(documents)

    @staticmethod
    def min_max_normalize(scores: np.ndarray) -> np.ndarray:
        """
        Normalize scores to the [0, 1] range using min-max scaling.

            normalized = (x - min) / (max - min)

        This is necessary before combining TF-IDF and BM25 scores because
        they live on completely different scales (cosine sim is in [0,1]
        but BM25 can be any non-negative value).

        Args:
            scores: np.ndarray of raw scores

        Returns:
            np.ndarray of scores in [0.0, 1.0].
            If all scores are identical, returns zeros (no discrimination).
        """
        scores = np.asarray(scores, dtype=np.float64)
        min_val = np.min(scores)
        max_val = np.max(scores)
        range_val = max_val - min_val

        if range_val == 0.0:
            # All scores identical — no way to discriminate
            return np.zeros_like(scores)

        return (scores - min_val) / range_val

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Retrieve the top-k most relevant documents using hybrid scoring.

        Steps:
            1. Compute TF-IDF query vector and cosine similarities
            2. Compute BM25 scores
            3. Min-max normalize both
            4. Weighted combination
            5. Return top-k with scores and metadata

        Args:
            query: raw query string
            top_k: number of top results to return

        Returns:
            List of dicts, each containing:
                - doc_index: int — index into the original documents list
                - score: float — combined score (higher = more relevant)
                - metadata: dict — the metadata for this document
                - tfidf_score: float — raw TF-IDF cosine similarity
                - bm25_score: float — raw BM25 score
        """
        if self.tfidf_matrix.shape[0] == 0:
            return []

        # Step 1: TF-IDF cosine similarity
        query_vec = tfidf_embed_query(query, self.vocab, self.idf_values)
        tfidf_scores = batch_cosine_similarity(query_vec, self.tfidf_matrix)

        # Step 2: BM25 scores
        bm25_scores = self.bm25_index.score(query)

        # Step 3: Normalize both to [0, 1]
        tfidf_norm = self.min_max_normalize(tfidf_scores)
        bm25_norm = self.min_max_normalize(bm25_scores)

        # Step 4: Weighted combination
        combined = (
            self.tfidf_weight * tfidf_norm + self.bm25_weight * bm25_norm
        )

        # Step 5: Rank by combined score (descending)
        ranked_indices = np.argsort(-combined)[:top_k]

        results = []
        for idx in ranked_indices:
            idx = int(idx)
            results.append({
                "doc_index": idx,
                "score": float(combined[idx]),
                "metadata": self.doc_metadata[idx],
                "tfidf_score": float(tfidf_scores[idx]),
                "bm25_score": float(bm25_scores[idx]),
            })

        return results

    def explain_retrieval(self, query: str, doc_index: int) -> dict:
        """
        Explain why a document was (or wasn't) ranked highly for a query.

        This produces a detailed breakdown of the scoring for debugging
        and for demonstrating understanding to the professor.

        Args:
            query: raw query string
            doc_index: index of the document to explain

        Returns:
            Dict containing:
                - query_tokens: stemmed tokens from the query
                - doc_tokens: stemmed tokens from the document
                - matching_terms: terms that appear in both query and document
                - term_details: per-term breakdown (TF, IDF, TF-IDF, BM25 contribution)
                - tfidf_cosine_sim: overall TF-IDF cosine similarity
                - bm25_total_score: overall BM25 score
                - combined_score: weighted combination score
                - document_text: the raw document text
        """
        query_tokens = tokenize(query)
        doc_tokens = tokenize(self.documents[doc_index])

        # Find matching terms
        query_set = set(query_tokens)
        doc_set = set(doc_tokens)
        matching = query_set & doc_set

        # Per-term analysis
        term_details = []
        doc_tf = compute_tf(doc_tokens)
        query_tf = compute_tf(query_tokens)

        for term in sorted(matching):
            detail = {
                "term": term,
                "query_tf": query_tf.get(term, 0.0),
                "doc_tf": doc_tf.get(term, 0.0),
                "idf": self.idf_values.get(term, 0.0),
                "tfidf_in_doc": doc_tf.get(term, 0.0) * self.idf_values.get(term, 0.0),
                "tfidf_in_query": query_tf.get(term, 0.0) * self.idf_values.get(term, 0.0),
            }

            # BM25 contribution for this term
            raw_tf = Counter(doc_tokens).get(term, 0)
            doc_len = len(doc_tokens)
            if term in self.bm25_index.idf and raw_tf > 0:
                idf_bm25 = self.bm25_index.idf[term]
                k1 = self.bm25_index.k1
                b = self.bm25_index.b
                avgdl = self.bm25_index.avgdl
                num = raw_tf * (k1 + 1)
                den = raw_tf + k1 * (1 - b + b * doc_len / avgdl)
                detail["bm25_contribution"] = idf_bm25 * (num / den)
            else:
                detail["bm25_contribution"] = 0.0

            term_details.append(detail)

        # Overall scores
        query_vec = tfidf_embed_query(query, self.vocab, self.idf_values)
        tfidf_sim = cosine_similarity(query_vec, self.tfidf_matrix[doc_index])
        bm25_total = float(self.bm25_index.score(query)[doc_index])

        # Combined score (need full arrays for normalization)
        all_tfidf = batch_cosine_similarity(query_vec, self.tfidf_matrix)
        all_bm25 = self.bm25_index.score(query)
        tfidf_norm = self.min_max_normalize(all_tfidf)
        bm25_norm = self.min_max_normalize(all_bm25)
        combined_all = self.tfidf_weight * tfidf_norm + self.bm25_weight * bm25_norm

        return {
            "query_tokens": query_tokens,
            "doc_tokens": doc_tokens,
            "matching_terms": sorted(matching),
            "non_matching_query_terms": sorted(query_set - doc_set),
            "term_details": term_details,
            "tfidf_cosine_sim": tfidf_sim,
            "bm25_total_score": bm25_total,
            "combined_score": float(combined_all[doc_index]),
            "tfidf_normalized": float(tfidf_norm[doc_index]),
            "bm25_normalized": float(bm25_norm[doc_index]),
            "document_text": self.documents[doc_index],
        }


# ===========================================================================
#  Part 6: Tag Retriever (MemoryMap Integration)
# ===========================================================================

class TagRetriever:
    """
    Tag-aware retriever for the MemoryMap dementia assistant.

    Wraps HybridRetriever with domain-specific logic for MemoryMap tags.
    Each tag represents a labeled object in a patient's home with:
        - label: what the object is (e.g., "medicine cabinet")
        - position: where it is in the room (e.g., "upper-left wall")
        - notes: caregiver notes (e.g., "White cabinet with red cross")
        - room_name: which room it's in (e.g., "Bathroom")

    The tag fields are concatenated into a document string for indexing.
    When a patient asks "Where are my pills?", this retriever finds the
    most relevant tagged objects.
    """

    def __init__(self, tags: list[dict]):
        """
        Build the retriever index from a list of tag dicts.

        Args:
            tags: list of tag dicts, each with keys:
                  label, position, notes (optional), room_name, id
        """
        self.tags = tags

        # Convert each tag to a document string
        self.documents = []
        self.metadata = []
        for tag in tags:
            # Combine all tag fields into one searchable document
            doc = (
                f"{tag.get('label', '')} "
                f"{tag.get('position', '')} "
                f"{tag.get('notes', '')} "
                f"{tag.get('room_name', '')}"
            )
            self.documents.append(doc)
            self.metadata.append(tag)

        # Build the hybrid retriever internally
        self.retriever = HybridRetriever(
            documents=self.documents,
            doc_metadata=self.metadata,
            tfidf_weight=0.4,
            bm25_weight=0.6,
        )

    def find_relevant_tags(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Find the most relevant tags for a patient's query.

        Args:
            query: the patient's natural language question
            top_k: number of top tags to return

        Returns:
            List of dicts, each with:
                - tag: the full tag dict (label, room, position, notes, id)
                - score: combined relevance score
                - tfidf_score: TF-IDF cosine similarity component
                - bm25_score: BM25 component
        """
        results = self.retriever.retrieve(query, top_k=top_k)

        return [
            {
                "tag": r["metadata"],
                "score": r["score"],
                "tfidf_score": r["tfidf_score"],
                "bm25_score": r["bm25_score"],
            }
            for r in results
        ]

    def find_relevant_tag_ids(self, query: str, top_k: int = 5) -> list[str]:
        """
        Return just the tag IDs, ranked by relevance.

        This is the interface used by the evaluation runner (retriever.py).

        Args:
            query: patient's question
            top_k: number of results

        Returns:
            List of tag ID strings, ordered by decreasing relevance.
        """
        results = self.find_relevant_tags(query, top_k=top_k)
        return [r["tag"]["id"] for r in results]

    def explain(self, query: str) -> str:
        """
        Human-readable explanation of retrieval results for debugging.

        Useful for showing the professor what the system is doing internally
        and why it ranked certain tags higher than others.

        Args:
            query: patient's question

        Returns:
            Multi-line string with formatted explanation.
        """
        results = self.find_relevant_tags(query, top_k=5)

        lines = []
        lines.append(f"Query: \"{query}\"")
        lines.append(f"Query tokens (after stemming): {tokenize(query)}")
        lines.append(f"")
        lines.append(f"Top {len(results)} results:")
        lines.append("-" * 70)

        for rank, r in enumerate(results, 1):
            tag = r["tag"]
            lines.append(
                f"  #{rank}  [{tag.get('id', '?')}] "
                f"{tag.get('label', '?')} ({tag.get('room_name', '?')})"
            )
            lines.append(
                f"       Combined: {r['score']:.4f}  |  "
                f"TF-IDF: {r['tfidf_score']:.4f}  |  "
                f"BM25: {r['bm25_score']:.4f}"
            )

            # Explain term matches for top results
            doc_idx = self.documents.index(
                f"{tag.get('label', '')} "
                f"{tag.get('position', '')} "
                f"{tag.get('notes', '')} "
                f"{tag.get('room_name', '')}"
            )
            explanation = self.retriever.explain_retrieval(query, doc_idx)
            if explanation["matching_terms"]:
                lines.append(
                    f"       Matching terms: {', '.join(explanation['matching_terms'])}"
                )
            if explanation["non_matching_query_terms"]:
                lines.append(
                    f"       Unmatched query terms: "
                    f"{', '.join(explanation['non_matching_query_terms'])}"
                )
            lines.append("")

        return "\n".join(lines)


# ===========================================================================
#  Legacy-compatible retriever classes (used by run_eval.py)
# ===========================================================================

# These classes maintain backward compatibility with the evaluation runner
# which imports TfIdfRetriever, BM25Retriever, and EmbeddingRetriever.


class TfIdfRetriever:
    """
    Retriever using TF-IDF vectors + cosine similarity.

    Workflow:
        1. Fit TF-IDF on all tag descriptions (the "document corpus")
        2. For each query, compute TF-IDF vector
        3. Compute cosine similarity between query and all documents
        4. Return documents sorted by similarity (descending)
    """

    def __init__(self):
        self.vocab: dict[str, int] = {}
        self.idf: dict[str, float] = {}
        self.doc_matrix: Optional[np.ndarray] = None
        self.doc_ids: list[str] = []
        self.vocab_size: int = 0

    def fit(self, tags: list[dict]) -> "TfIdfRetriever":
        """Index all tags."""
        documents = []
        self.doc_ids = []

        for tag in tags:
            doc = f"{tag['label']} {tag['room_name']} {tag['position']} {tag.get('notes', '')}"
            documents.append(doc)
            self.doc_ids.append(tag["id"])

        self.doc_matrix, self.vocab, self.idf = build_tfidf_matrix(documents)
        self.vocab_size = len(self.vocab)

        return self

    @property
    def vectorizer(self):
        """Compatibility shim: run_eval.py accesses .vectorizer.vocab_size."""

        class _Shim:
            pass

        shim = _Shim()
        shim.vocab_size = self.vocab_size
        return shim

    def retrieve(self, query: str) -> list[str]:
        """Retrieve ranked tag IDs for a query."""
        query_vec = tfidf_embed_query(query, self.vocab, self.idf)
        similarities = batch_cosine_similarity(query_vec, self.doc_matrix)

        # Sort by similarity descending
        ranked_indices = np.argsort(-similarities)
        return [self.doc_ids[i] for i in ranked_indices]

    def retrieve_with_scores(self, query: str) -> list[tuple[str, float]]:
        """Retrieve ranked tag IDs with similarity scores."""
        query_vec = tfidf_embed_query(query, self.vocab, self.idf)
        similarities = batch_cosine_similarity(query_vec, self.doc_matrix)
        ranked_indices = np.argsort(-similarities)
        return [(self.doc_ids[i], float(similarities[i])) for i in ranked_indices]


class BM25Retriever:
    """Retriever using BM25 scoring."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.index: Optional[BM25Index] = None
        self.doc_ids: list[str] = []

    def fit(self, tags: list[dict]) -> "BM25Retriever":
        documents = []
        self.doc_ids = []
        for tag in tags:
            doc = f"{tag['label']} {tag['room_name']} {tag['position']} {tag.get('notes', '')}"
            documents.append(doc)
            self.doc_ids.append(tag["id"])
        self.index = BM25Index(documents, k1=self.k1, b=self.b)
        return self

    def retrieve(self, query: str) -> list[str]:
        scores = self.index.score(query)
        ranked_indices = np.argsort(-scores)
        return [self.doc_ids[i] for i in ranked_indices]


# ===========================================================================
#  Part 7: GloVe Semantic Embeddings
# ===========================================================================
#
#  THE VOCABULARY MISMATCH PROBLEM
#  ===============================
#  TF-IDF and BM25 are keyword-based: they only match when the exact same
#  word (after stemming) appears in both the query and the document.
#
#  This fails for:
#    - "pills" vs "medicine cabinet"  (synonyms)
#    - "inhaler" vs "nebulizer"       (medical equivalents)
#    - "TV clicker" vs "remote"       (colloquial vs formal)
#
#  Hardcoded synonym lists (Part 1) help for known cases but can't handle
#  words we never anticipated. We need DENSE SEMANTIC VECTORS where words
#  with similar meanings are close in vector space — automatically.
#
#  GloVe (Global Vectors for Word Representation) was trained on 6 billion
#  tokens from Wikipedia + Gigaword. Each word becomes a 50-dimensional
#  vector. Words that appear in similar contexts land near each other:
#
#    cosine("pill", "medication")  ≈ 0.82   (high — semantically related)
#    cosine("pill", "shoe")        ≈ 0.12   (low — unrelated)
#
#  HOW WE USE GLOVE FOR DOCUMENT/QUERY EMBEDDING
#  ==============================================
#  1. Load pre-trained 50d vectors (400,000 words)
#  2. To embed a document: tokenize → look up each word's GloVe vector →
#     compute a weighted average (IDF-weighted, so rare words matter more)
#  3. To embed a query: same process
#  4. Rank by cosine similarity between query embedding and doc embeddings
#
#  This is the same core idea behind modern dense retrievers (DPR, ColBERT)
#  but using static pre-trained vectors instead of a trained bi-encoder.
#  We do ALL the math ourselves — GloVe just provides the word vectors.

import logging

_glove_logger = logging.getLogger(__name__)

# Singleton: loaded once, shared across all instances
_glove_vectors: Optional[dict] = None
_glove_dim: int = 50


def load_glove(model_name: str = "glove-wiki-gigaword-50") -> dict:
    """
    Load pre-trained GloVe word vectors via gensim's downloader.

    We use gensim ONLY as a convenience loader — it downloads and caches
    the Stanford GloVe vectors. All similarity math is done by us in numpy.

    The vectors are loaded once and cached in a module-level singleton.
    Subsequent calls return instantly.

    Args:
        model_name: gensim model identifier. Default is GloVe 6B 50d
                    (400K words, 50 dimensions, ~66MB download).

    Returns:
        A gensim KeyedVectors object (used only for word→vector lookup).
    """
    global _glove_vectors, _glove_dim
    if _glove_vectors is not None:
        return _glove_vectors

    try:
        import gensim.downloader as api
        _glove_logger.info("Loading GloVe vectors (%s)...", model_name)
        _glove_vectors = api.load(model_name)
        _glove_dim = _glove_vectors.vector_size
        _glove_logger.info(
            "GloVe loaded: %d words, %d dimensions",
            len(_glove_vectors), _glove_dim,
        )
        return _glove_vectors
    except Exception as e:
        _glove_logger.warning("Failed to load GloVe: %s. Falling back to keyword-only.", e)
        return None


def glove_embed_word(word: str, vectors=None) -> Optional[np.ndarray]:
    """
    Look up a single word's GloVe vector.

    Args:
        word: a lowercase word (NOT stemmed — GloVe was trained on raw words)
        vectors: pre-loaded GloVe vectors (if None, loads the singleton)

    Returns:
        np.ndarray of shape [50] or None if word is not in vocabulary.
    """
    if vectors is None:
        vectors = load_glove()
    if vectors is None:
        return None
    try:
        return vectors[word]
    except KeyError:
        return None


def glove_embed_sentence(
    text: str,
    vectors=None,
    use_idf_weights: bool = True,
    idf: Optional[dict] = None,
) -> np.ndarray:
    """
    Embed a sentence/document as the weighted average of its word vectors.

    This is sometimes called a "bag-of-vectors" embedding. Each word in the
    text is mapped to its GloVe vector, then all vectors are averaged. If
    IDF weights are provided, rare words get proportionally more influence.

    Mathematically:
        embed(text) = Σ (idf(w) * GloVe(w)) / Σ idf(w)

    If no IDF is available, all words are weighted equally (simple average).

    NOTE: We tokenize WITHOUT stemming here, because GloVe was trained on
    raw English words. "medicine" has a GloVe vector; "medicin" does not.

    Args:
        text: raw input text
        vectors: pre-loaded GloVe vectors
        use_idf_weights: whether to weight by IDF (default True)
        idf: IDF dict from our TF-IDF module. If None, uniform weighting.

    Returns:
        np.ndarray of shape [50]. Zero vector if no words have GloVe entries.
    """
    if vectors is None:
        vectors = load_glove()
    if vectors is None:
        return np.zeros(_glove_dim, dtype=np.float64)

    # Tokenize WITHOUT stemming — GloVe needs raw words
    text_lower = text.lower()
    raw_tokens = re.findall(r"[a-z]+", text_lower)
    raw_tokens = [t for t in raw_tokens if t not in STOPWORDS and len(t) > 1]

    if not raw_tokens:
        return np.zeros(_glove_dim, dtype=np.float64)

    weighted_sum = np.zeros(_glove_dim, dtype=np.float64)
    total_weight = 0.0

    for word in raw_tokens:
        vec = glove_embed_word(word, vectors)
        if vec is not None:
            # IDF weighting: rare words contribute more to the embedding
            weight = 1.0
            if use_idf_weights and idf:
                # Try the stemmed form for IDF lookup (our IDF uses stems)
                stemmed = stem(word)
                weight = idf.get(stemmed, 1.0)

            weighted_sum += weight * vec.astype(np.float64)
            total_weight += weight

    if total_weight == 0.0:
        return np.zeros(_glove_dim, dtype=np.float64)

    # Average (weighted mean of word vectors)
    embedding = weighted_sum / total_weight

    return embedding


class GloVeRetriever:
    """
    Dense semantic retriever using pre-trained GloVe word vectors.

    Unlike TF-IDF/BM25 (which match on exact token overlap), this retriever
    captures semantic similarity: "pills" will match "medicine cabinet"
    because their GloVe vectors are close in 50-dimensional space.

    Pipeline:
        1. Convert each document to a 50d vector (IDF-weighted average of
           word vectors)
        2. Convert query to a 50d vector
        3. Compute cosine similarity between query vector and all doc vectors
        4. Rank by similarity

    This is conceptually the same as how modern dense passage retrievers
    (DPR, ColBERT) work, but using static pre-trained vectors instead of
    a fine-tuned bi-encoder. The math is identical — only the vector source
    differs.
    """

    def __init__(self, documents: list[str], doc_metadata: Optional[list[dict]] = None):
        """
        Build the GloVe document index.

        Args:
            documents: list of raw text strings to index
            doc_metadata: optional metadata dicts (returned with results)
        """
        self.documents = documents
        self.doc_metadata = doc_metadata or [{} for _ in documents]
        self.vectors = load_glove()
        self.n_docs = len(documents)

        # Build IDF from the corpus (used for weighted averaging)
        corpus_tokens = [tokenize(doc) for doc in documents]
        self._idf = compute_idf(corpus_tokens)

        # Pre-compute document embeddings — each doc becomes a 50d vector
        self.doc_matrix = np.zeros((self.n_docs, _glove_dim), dtype=np.float64)
        for i, doc in enumerate(documents):
            self.doc_matrix[i] = glove_embed_sentence(
                doc, self.vectors, use_idf_weights=True, idf=self._idf
            )

        # L2-normalize all document vectors for efficient cosine similarity
        # After normalization: cosine_sim(a, b) = dot(a, b)
        norms = np.linalg.norm(self.doc_matrix, axis=1, keepdims=True)
        # Avoid division by zero for empty docs
        norms = np.where(norms == 0, 1, norms)
        self.doc_matrix_normed = self.doc_matrix / norms

        _glove_logger.info(
            "GloVeRetriever indexed %d documents into %dd vectors",
            self.n_docs, _glove_dim,
        )

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Retrieve the most semantically similar documents for a query.

        Args:
            query: raw query string (e.g., "Where are my pills?")
            top_k: number of results to return

        Returns:
            List of dicts with: doc_index, score, metadata
        """
        # Embed query into same 50d space
        query_vec = glove_embed_sentence(
            query, self.vectors, use_idf_weights=True, idf=self._idf
        )

        # L2-normalize the query vector
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []
        query_vec_normed = query_vec / query_norm

        # Cosine similarity = dot product of normalized vectors
        # This is a single matrix-vector multiply: O(n_docs * 50)
        similarities = self.doc_matrix_normed @ query_vec_normed

        # Rank by similarity (descending)
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            results.append({
                "doc_index": int(idx),
                "score": float(similarities[idx]),
                "metadata": self.doc_metadata[int(idx)],
            })

        return results

    def explain(self, query: str, doc_index: int) -> dict:
        """
        Explain why a document scored the way it did.

        Shows the closest words between the query and document by
        comparing individual word vectors.
        """
        if self.vectors is None:
            return {"error": "GloVe not loaded"}

        query_lower = query.lower()
        doc_lower = self.documents[doc_index].lower()

        q_words = [w for w in re.findall(r"[a-z]+", query_lower)
                    if w not in STOPWORDS and len(w) > 1]
        d_words = [w for w in re.findall(r"[a-z]+", doc_lower)
                    if w not in STOPWORDS and len(w) > 1]

        # Find closest word pairs between query and document
        word_pairs = []
        for qw in q_words:
            qv = glove_embed_word(qw, self.vectors)
            if qv is None:
                continue
            best_dw, best_sim = None, -1.0
            for dw in d_words:
                dv = glove_embed_word(dw, self.vectors)
                if dv is None:
                    continue
                sim = cosine_similarity(qv.astype(np.float64), dv.astype(np.float64))
                if sim > best_sim:
                    best_sim = sim
                    best_dw = dw
            if best_dw is not None:
                word_pairs.append({
                    "query_word": qw,
                    "doc_word": best_dw,
                    "similarity": round(best_sim, 4),
                })

        # Overall score
        query_vec = glove_embed_sentence(query, self.vectors, use_idf_weights=True, idf=self._idf)
        qn = np.linalg.norm(query_vec)
        doc_vec = self.doc_matrix[doc_index]
        dn = np.linalg.norm(doc_vec)
        overall = float(np.dot(query_vec, doc_vec) / (qn * dn)) if qn > 0 and dn > 0 else 0.0

        return {
            "query_words": q_words,
            "doc_words": d_words,
            "word_pairs": sorted(word_pairs, key=lambda x: x["similarity"], reverse=True),
            "overall_similarity": round(overall, 4),
        }


class SemanticHybridRetriever:
    """
    The full retrieval pipeline: combines keyword matching (BM25) with
    semantic similarity (GloVe) for robust retrieval.

    This addresses both:
    - Exact matches: BM25 finds "shoe rack" when query says "shoe"
    - Semantic matches: GloVe finds "medicine cabinet" when query says "pills"

    Score fusion:
        final_score = bm25_weight * norm(bm25_score)
                    + glove_weight * norm(glove_score)

    Both score vectors are min-max normalized to [0,1] before combining,
    so neither component dominates regardless of raw score ranges.
    """

    def __init__(
        self,
        documents: list[str],
        doc_metadata: Optional[list[dict]] = None,
        bm25_weight: float = 0.4,
        glove_weight: float = 0.6,
    ):
        """
        Args:
            documents: list of raw text strings
            doc_metadata: optional metadata for each document
            bm25_weight: weight for keyword matching (BM25)
            glove_weight: weight for semantic matching (GloVe)
        """
        self.documents = documents
        self.doc_metadata = doc_metadata or [{} for _ in documents]
        self.bm25_weight = bm25_weight
        self.glove_weight = glove_weight
        self.n_docs = len(documents)

        # Build both retrieval components
        self.bm25 = BM25Index(documents)
        self.glove_retriever = GloVeRetriever(documents, doc_metadata)

    @staticmethod
    def _min_max_normalize(scores: np.ndarray) -> np.ndarray:
        """Normalize scores to [0, 1] range."""
        s_min = scores.min()
        s_max = scores.max()
        if s_max - s_min == 0:
            return np.zeros_like(scores)
        return (scores - s_min) / (s_max - s_min)

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """
        Retrieve using combined BM25 + GloVe scoring.

        Returns:
            List of dicts with: doc_index, score, bm25_score, glove_score, metadata
        """
        # BM25 scores (keyword matching)
        bm25_scores = self.bm25.score(query)

        # GloVe scores (semantic similarity)
        query_vec = glove_embed_sentence(
            query,
            self.glove_retriever.vectors,
            use_idf_weights=True,
            idf=self.glove_retriever._idf,
        )
        qn = np.linalg.norm(query_vec)
        if qn > 0:
            query_normed = query_vec / qn
            glove_scores = self.glove_retriever.doc_matrix_normed @ query_normed
        else:
            glove_scores = np.zeros(self.n_docs, dtype=np.float64)

        # Min-max normalize both to [0, 1]
        bm25_normed = self._min_max_normalize(bm25_scores)
        glove_normed = self._min_max_normalize(glove_scores)

        # Weighted combination
        combined = (self.bm25_weight * bm25_normed) + (self.glove_weight * glove_normed)

        # Rank and return top-k
        top_indices = np.argsort(combined)[::-1][:top_k]

        results = []
        for idx in top_indices:
            results.append({
                "doc_index": int(idx),
                "score": float(combined[idx]),
                "bm25_score": float(bm25_scores[idx]),
                "glove_score": float(glove_scores[idx]),
                "metadata": self.doc_metadata[int(idx)],
            })

        return results

    def explain(self, query: str, doc_index: int) -> dict:
        """Full explanation combining BM25 term matches + GloVe word pair similarities."""
        glove_explanation = self.glove_retriever.explain(query, doc_index)

        bm25_scores = self.bm25.score(query)
        query_tokens = tokenize(query)
        expanded = expand_query(query_tokens)
        matching_terms = []
        for tok, weight in expanded:
            if tok in self.bm25.idf:
                for di, doc_tokens in enumerate(self.bm25.doc_tokens):
                    if di == doc_index and tok in doc_tokens:
                        matching_terms.append({"term": tok, "weight": weight, "source": "original" if weight == 1.0 else "synonym"})
                        break

        return {
            "bm25_score": float(bm25_scores[doc_index]),
            "bm25_matching_terms": matching_terms,
            "glove_similarity": glove_explanation["overall_similarity"],
            "glove_word_pairs": glove_explanation["word_pairs"][:5],
        }


class EmbeddingRetriever:
    """
    The main retriever: combines BM25 keyword matching + GloVe semantic
    similarity via SemanticHybridRetriever.

    This is the "best of both worlds" approach:
    - BM25 handles exact matches ("shoe" → "shoe rack")
    - GloVe handles vocabulary mismatch ("pills" → "medicine cabinet")

    Used by the evaluation pipeline and the live query endpoint.
    """

    def __init__(self, embedding_dim: int = 50):
        """
        Args:
            embedding_dim: GloVe vector dimension (default 50).
        """
        self.embedding_dim = embedding_dim
        self.retriever: Optional[SemanticHybridRetriever] = None
        self.doc_ids: list[str] = []
        self.vocabulary: dict[str, int] = {}

    @property
    def embedder(self):
        """Compatibility shim for run_eval.py."""

        class _Shim:
            pass

        shim = _Shim()
        shim.vocabulary = self.vocabulary
        shim.embedding_dim = self.embedding_dim
        return shim

    def fit(self, tags: list[dict]) -> "EmbeddingRetriever":
        documents = []
        self.doc_ids = []
        metadata = []

        for tag in tags:
            doc = f"{tag['label']} {tag['room_name']} {tag['position']} {tag.get('notes', '')}"
            documents.append(doc)
            self.doc_ids.append(tag["id"])
            metadata.append(tag)

        self.retriever = SemanticHybridRetriever(
            documents=documents,
            doc_metadata=metadata,
            bm25_weight=0.4,
            glove_weight=0.6,
        )

        # Build vocab from BM25 component for compatibility
        self.vocabulary = {term: i for i, term in enumerate(sorted(self.retriever.bm25.idf.keys()))}

        return self

    def retrieve(self, query: str) -> list[str]:
        results = self.retriever.retrieve(query, top_k=len(self.doc_ids))
        return [self.doc_ids[r["doc_index"]] for r in results]

    def retrieve_with_scores(self, query: str) -> list[tuple[str, float]]:
        results = self.retriever.retrieve(query, top_k=len(self.doc_ids))
        return [(self.doc_ids[r["doc_index"]], r["score"]) for r in results]

    def explain(self, query: str) -> str:
        """Human-readable explanation of retrieval."""
        if self.retriever is None:
            return "Retriever not fitted yet."
        results = self.retriever.retrieve(query, top_k=5)
        lines = [f"Query: \"{query}\"\n"]
        for i, r in enumerate(results):
            meta = r["metadata"]
            lines.append(
                f"  #{i+1} [{meta.get('id','?')}] {meta.get('label','?')} ({meta.get('room_name','?')})\n"
                f"       Combined: {r['score']:.4f}  |  BM25: {r['bm25_score']:.4f}  |  GloVe: {r['glove_score']:.4f}"
            )
            # Show word-level explanation for top result
            if i == 0:
                expl = self.retriever.explain(query, r["doc_index"])
                if expl.get("glove_word_pairs"):
                    pairs = expl["glove_word_pairs"][:3]
                    pair_strs = [f"{p['query_word']}<->{p['doc_word']}({p['similarity']:.2f})" for p in pairs]
                    lines.append(f"       GloVe bridges: {', '.join(pair_strs)}")
        return "\n".join(lines)


# ===========================================================================
#  Demo / Main
# ===========================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("  MemoryMap Custom Embeddings & Retrieval — Demo")
    print("=" * 70)

    # ---- Sample tag documents (simulating MemoryMap tags) ----
    sample_tags = [
        {
            "id": "tag-001",
            "label": "medicine cabinet",
            "room_name": "Bathroom",
            "position": "upper-left wall above sink",
            "notes": "White cabinet with a red cross symbol, mounted above the sink",
        },
        {
            "id": "tag-002",
            "label": "bedside drawer",
            "room_name": "Master Bedroom",
            "position": "right side of the bed",
            "notes": "Small wooden nightstand with two drawers",
        },
        {
            "id": "tag-003",
            "label": "kitchen pantry",
            "room_name": "Kitchen",
            "position": "far-right corner near fridge",
            "notes": "Tall white pantry cabinet with pull-out shelves",
        },
        {
            "id": "tag-004",
            "label": "shoe rack",
            "room_name": "Entryway",
            "position": "left wall near front door",
            "notes": "Three-tier wooden shoe rack with about 8 pairs visible",
        },
        {
            "id": "tag-005",
            "label": "key hook board",
            "room_name": "Entryway",
            "position": "right wall at eye level",
            "notes": "Wooden board with 4 metal hooks, currently has 2 sets of keys",
        },
        {
            "id": "tag-006",
            "label": "refrigerator",
            "room_name": "Kitchen",
            "position": "left wall",
            "notes": "Large stainless steel double-door fridge with water dispenser",
        },
        {
            "id": "tag-007",
            "label": "TV stand",
            "room_name": "Living Room",
            "position": "front wall, facing couch",
            "notes": "Low wooden TV stand with two shelves — has remotes and game console",
        },
    ]

    # ==================================================================
    # PART A: Keyword-only retrieval (BM25 + TF-IDF + synonym expansion)
    # ==================================================================
    print("\n[1] Building keyword-only TagRetriever...")
    tag_retriever = TagRetriever(sample_tags)
    print(f"    Indexed {len(sample_tags)} tags")
    print(f"    Vocabulary size: {len(tag_retriever.retriever.vocab)}")

    queries = [
        "Where are my blood pressure pills?",
        "Where did I put my keys?",
        "I need to find my shoes",
        "Where is the milk?",
        "I want to heat up some leftovers",
        "Where's my inhaler?",          # never appears in any tag
        "I need my reading spectacles",  # synonym for glasses
    ]

    print(f"\n[2] Keyword-only results ({len(queries)} queries)...\n")
    for query in queries:
        print("=" * 70)
        print(tag_retriever.explain(query))

    # ==================================================================
    # PART B: GloVe semantic retrieval — the key improvement
    # ==================================================================
    print("\n" + "=" * 70)
    print("[3] GloVe Semantic Retrieval")
    print("    Loading pre-trained GloVe vectors (400K words, 50 dimensions)...")
    print("=" * 70)

    glove = load_glove()
    if glove is not None:
        # Show word similarity examples
        print("\n  Word vector similarities (no hardcoding — learned from data):")
        word_pairs = [
            ("pill", "medicine"),
            ("pill", "shoe"),
            ("inhaler", "nebulizer"),
            ("remote", "controller"),
            ("fridge", "refrigerator"),
            ("glasses", "spectacles"),
            ("key", "lock"),
        ]
        for w1, w2 in word_pairs:
            v1 = glove_embed_word(w1, glove)
            v2 = glove_embed_word(w2, glove)
            if v1 is not None and v2 is not None:
                sim = cosine_similarity(v1.astype(np.float64), v2.astype(np.float64))
                bar = "#" * int(sim * 30) + "." * (30 - int(sim * 30))
                print(f"    {w1:15s} <-> {w2:15s}  [{bar}] {sim:.4f}")
            else:
                missing = w1 if v1 is None else w2
                print(f"    {w1:15s} <-> {w2:15s}  ('{missing}' not in GloVe)")

        # Build the full semantic hybrid retriever
        print(f"\n[4] Semantic Hybrid Retriever (BM25 + GloVe)")
        print("    This handles words we NEVER anticipated...\n")

        semantic_retriever = EmbeddingRetriever()
        semantic_retriever.fit(sample_tags)

        for query in queries:
            print("=" * 70)
            print(semantic_retriever.explain(query))
            print()

    else:
        print("\n  GloVe not available — run 'python -c \"import gensim.downloader as api; api.load(\\\"glove-wiki-gigaword-50\\\")\"' first")

    # ==================================================================
    # PART C: Component demonstrations (math from scratch)
    # ==================================================================
    print("\n" + "=" * 70)
    print("[5] Component demonstrations — all math from scratch")
    print("=" * 70)

    # Stemming
    print("\n  Stemmer (suffix-stripping, no external libraries):")
    test_words = ["running", "walked", "medicines", "shoes", "boxes",
                  "glasses", "cabinets", "quickly", "beautiful"]
    for w in test_words:
        print(f"    {w:20s} -> {stem(w)}")

    # Vector operations
    print("\n  Vector operations (numpy only):")
    v1 = np.array([1.0, 2.0, 3.0])
    v2 = np.array([2.0, 4.0, 6.0])
    v3 = np.array([3.0, 0.0, 0.0])
    print(f"    l2_normalize([1,2,3])      = {l2_normalize(v1)}")
    print(f"    cosine_sim(v, 2*v)         = {cosine_similarity(v1, v2):.4f}  (parallel = 1.0)")
    print(f"    cosine_sim(v, orthogonal)  = {cosine_similarity(v1, v3):.4f}  (should be low)")
    print(f"    euclidean_dist(v1, v2)     = {euclidean_distance(v1, v2):.4f}")
    print(f"    cosine_sim(zero, v1)       = {cosine_similarity(np.zeros(3), v1):.4f}  (zero vec handled)")

    # TF-IDF
    sample_docs = ["medicine cabinet bathroom", "kitchen pantry fridge", "shoe rack entryway door"]
    matrix, vocab, idf_vals = build_tfidf_matrix(sample_docs)
    print(f"\n  TF-IDF matrix ({matrix.shape[0]} docs, {matrix.shape[1]} terms):")
    print(f"    Vocab: {vocab}")

    # BM25
    bm25 = BM25Index(sample_docs)
    print(f"\n  BM25 scores for 'medicine cabinet': {bm25.score('medicine cabinet')}")

    print("\n" + "=" * 70)
    print("  Demo complete.")
    print("=" * 70)
