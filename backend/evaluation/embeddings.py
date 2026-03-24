"""
Custom embedding and retrieval implementations for MemoryMap RAG evaluation.

All implementations are from scratch — no external embedding APIs or libraries.
This demonstrates understanding of the underlying IR/NLP concepts:

1. TF-IDF Vectorizer — term frequency * inverse document frequency
2. BM25 Scorer — probabilistic retrieval model (Okapi BM25)
3. Cosine Similarity — angular distance between vectors
4. L2 Normalization — unit vector normalization
5. Custom Word Embeddings — co-occurrence based dense vectors via SVD

References:
    - TF-IDF: Salton & Buckley, 1988
    - BM25: Robertson & Zaragoza, 2009
    - SVD embeddings: Levy & Goldberg, 2014 (implicit factorization of PMI matrix)
"""

import math
import re
from collections import Counter
from typing import Optional


# ===========================================================================
#  Text preprocessing
# ===========================================================================

STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "must",
    "i", "me", "my", "mine", "we", "our", "you", "your", "he", "him",
    "his", "she", "her", "it", "its", "they", "them", "their",
    "what", "which", "who", "whom", "this", "that", "these", "those",
    "am", "in", "on", "at", "to", "for", "of", "with", "by", "from",
    "up", "about", "into", "through", "during", "before", "after",
    "above", "below", "between", "out", "off", "over", "under",
    "and", "but", "or", "nor", "not", "so", "very", "just",
    "than", "too", "also", "where", "when", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such",
    "no", "only", "own", "same", "then", "there", "here",
    "put", "find", "keep", "want", "get", "got", "going", "went",
})


def tokenize(text: str) -> list[str]:
    """
    Tokenize text into lowercase words, removing stopwords and punctuation.

    Steps:
        1. Lowercase
        2. Extract alphanumeric tokens via regex
        3. Remove stopwords
        4. Apply simple stemming (strip common suffixes)
    """
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    tokens = [t for t in tokens if t not in STOP_WORDS and len(t) > 1]
    # Simple suffix stemming (not full Porter, but demonstrates the concept)
    stemmed = []
    for t in tokens:
        if t.endswith("ing") and len(t) > 5:
            t = t[:-3]
        elif t.endswith("tion") and len(t) > 5:
            t = t[:-4] + "te"
        elif t.endswith("ies") and len(t) > 4:
            t = t[:-3] + "y"
        elif t.endswith("es") and len(t) > 4:
            t = t[:-2]
        elif t.endswith("s") and not t.endswith("ss") and len(t) > 3:
            t = t[:-1]
        stemmed.append(t)
    return stemmed


# ===========================================================================
#  L2 Normalization
# ===========================================================================

def l2_norm(vector: list[float]) -> float:
    """
    Compute the L2 (Euclidean) norm of a vector.

    ||v||₂ = sqrt(Σ vᵢ²)
    """
    return math.sqrt(sum(x * x for x in vector))


def l2_normalize(vector: list[float]) -> list[float]:
    """
    L2-normalize a vector to unit length.

    v_normalized = v / ||v||₂

    After normalization, cosine_similarity(a, b) = dot_product(a, b)
    which is computationally cheaper.
    """
    norm = l2_norm(vector)
    if norm == 0:
        return vector
    return [x / norm for x in vector]


# ===========================================================================
#  Cosine Similarity
# ===========================================================================

def dot_product(a: list[float], b: list[float]) -> float:
    """
    Compute dot product of two vectors.

    a · b = Σ aᵢ * bᵢ
    """
    return sum(x * y for x, y in zip(a, b))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    cos(θ) = (a · b) / (||a||₂ * ||b||₂)

    Returns value in [-1, 1]. Higher means more similar.
    For TF-IDF vectors (non-negative), range is [0, 1].
    """
    norm_a = l2_norm(a)
    norm_b = l2_norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot_product(a, b) / (norm_a * norm_b)


# ===========================================================================
#  TF-IDF Vectorizer (from scratch)
# ===========================================================================

class TfIdfVectorizer:
    """
    Term Frequency - Inverse Document Frequency vectorizer.

    TF-IDF captures how important a word is to a document relative to a corpus.

    TF(t, d) = count(t in d) / |d|                    (term frequency)
    IDF(t) = log(N / (1 + df(t)))                      (inverse document frequency)
    TF-IDF(t, d) = TF(t, d) * IDF(t)

    The +1 in IDF denominator prevents division by zero (Laplace smoothing).
    """

    def __init__(self):
        self.vocabulary: dict[str, int] = {}  # term -> index
        self.idf: dict[str, float] = {}       # term -> IDF score
        self.doc_count: int = 0

    def fit(self, documents: list[str]) -> "TfIdfVectorizer":
        """
        Learn vocabulary and IDF weights from a corpus of documents.

        Args:
            documents: list of text strings (each is one "document")
        """
        self.doc_count = len(documents)

        # Count document frequency for each term
        df: Counter = Counter()
        all_terms: set[str] = set()

        for doc in documents:
            tokens = tokenize(doc)
            unique_tokens = set(tokens)
            for token in unique_tokens:
                df[token] += 1
            all_terms.update(unique_tokens)

        # Build vocabulary (sorted for deterministic ordering)
        self.vocabulary = {term: idx for idx, term in enumerate(sorted(all_terms))}

        # Compute IDF for each term
        # IDF(t) = log(N / (1 + df(t)))
        self.idf = {}
        for term, freq in df.items():
            self.idf[term] = math.log(self.doc_count / (1 + freq))

        return self

    def transform(self, text: str) -> list[float]:
        """
        Convert a single text into a TF-IDF vector.

        Args:
            text: input text string

        Returns:
            list of floats — TF-IDF vector (length = vocabulary size)
        """
        tokens = tokenize(text)
        if not tokens:
            return [0.0] * len(self.vocabulary)

        # Compute term frequency
        tf: Counter = Counter(tokens)
        doc_len = len(tokens)

        # Build TF-IDF vector
        vector = [0.0] * len(self.vocabulary)
        for term, count in tf.items():
            if term in self.vocabulary:
                tf_score = count / doc_len
                idf_score = self.idf.get(term, 0.0)
                vector[self.vocabulary[term]] = tf_score * idf_score

        return vector

    def transform_normalized(self, text: str) -> list[float]:
        """Transform text to L2-normalized TF-IDF vector."""
        return l2_normalize(self.transform(text))

    @property
    def vocab_size(self) -> int:
        return len(self.vocabulary)


# ===========================================================================
#  BM25 Scorer (from scratch)
# ===========================================================================

class BM25Scorer:
    """
    Okapi BM25 — a probabilistic retrieval model.

    BM25 improves on TF-IDF by:
    1. Saturating term frequency (diminishing returns for repeated terms)
    2. Normalizing by document length

    BM25(q, d) = Σ IDF(t) * (TF(t,d) * (k1 + 1)) / (TF(t,d) + k1 * (1 - b + b * |d|/avgdl))

    Parameters:
        k1: term frequency saturation parameter (default 1.5)
            Higher k1 = more weight to term frequency
        b: document length normalization (default 0.75)
            b=0 means no length normalization, b=1 means full normalization
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.doc_tokens: list[list[str]] = []
        self.doc_ids: list[str] = []
        self.avgdl: float = 0.0
        self.doc_count: int = 0
        self.df: Counter = Counter()  # document frequency
        self.idf: dict[str, float] = {}

    def fit(self, documents: list[str], doc_ids: list[str]) -> "BM25Scorer":
        """
        Index a corpus of documents.

        Args:
            documents: list of text strings
            doc_ids: corresponding document/tag IDs
        """
        self.doc_ids = doc_ids
        self.doc_count = len(documents)
        self.doc_tokens = []

        total_len = 0
        self.df = Counter()

        for doc in documents:
            tokens = tokenize(doc)
            self.doc_tokens.append(tokens)
            total_len += len(tokens)

            # Count unique terms per document
            for term in set(tokens):
                self.df[term] += 1

        self.avgdl = total_len / self.doc_count if self.doc_count > 0 else 1.0

        # Compute IDF using the BM25 formula variant:
        # IDF(t) = log((N - df(t) + 0.5) / (df(t) + 0.5) + 1)
        # This variant avoids negative IDF for very common terms
        for term, freq in self.df.items():
            numerator = self.doc_count - freq + 0.5
            denominator = freq + 0.5
            self.idf[term] = math.log(numerator / denominator + 1)

        return self

    def score(self, query: str) -> list[tuple[str, float]]:
        """
        Score all documents against a query.

        Args:
            query: the search query text

        Returns:
            list of (doc_id, score) tuples sorted by score descending
        """
        query_tokens = tokenize(query)
        scores = []

        for i, doc_tokens in enumerate(self.doc_tokens):
            doc_len = len(doc_tokens)
            tf = Counter(doc_tokens)
            score = 0.0

            for q_term in query_tokens:
                if q_term not in self.idf:
                    continue

                term_freq = tf.get(q_term, 0)
                idf = self.idf[q_term]

                # BM25 TF component with saturation and length normalization
                numerator = term_freq * (self.k1 + 1)
                denominator = term_freq + self.k1 * (
                    1 - self.b + self.b * doc_len / self.avgdl
                )
                score += idf * (numerator / denominator)

            scores.append((self.doc_ids[i], score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def retrieve(self, query: str) -> list[str]:
        """Score and return ranked list of doc IDs."""
        return [doc_id for doc_id, _ in self.score(query)]


# ===========================================================================
#  Co-occurrence Embeddings via SVD (from scratch)
# ===========================================================================

class CooccurrenceEmbeddings:
    """
    Dense word embeddings via co-occurrence matrix + SVD decomposition.

    This is the core idea behind methods like GloVe and LSA:
    1. Build a term-term co-occurrence matrix from the corpus
    2. Apply Positive Pointwise Mutual Information (PPMI) weighting
    3. Reduce dimensionality via truncated SVD
    4. The resulting dense vectors capture semantic similarity

    For document embeddings, we average the word vectors (bag-of-embeddings).

    Note: We implement a simple SVD via the power iteration method rather than
    using numpy.linalg.svd, to show we understand the math. For production,
    you'd use numpy/scipy.
    """

    def __init__(self, embedding_dim: int = 32, window_size: int = 3):
        """
        Args:
            embedding_dim: number of dimensions in the output vectors
            window_size: context window for co-occurrence counting
        """
        self.embedding_dim = embedding_dim
        self.window_size = window_size
        self.vocabulary: dict[str, int] = {}
        self.word_vectors: dict[str, list[float]] = {}

    def fit(self, documents: list[str]) -> "CooccurrenceEmbeddings":
        """
        Build co-occurrence matrix from corpus and compute embeddings.

        Steps:
            1. Tokenize all documents
            2. Build vocabulary
            3. Count co-occurrences within sliding window
            4. Apply PPMI transformation
            5. Reduce via SVD to get dense vectors
        """
        # Tokenize all documents
        all_token_lists = [tokenize(doc) for doc in documents]
        all_tokens_flat = [t for tokens in all_token_lists for t in tokens]

        # Build vocabulary from all tokens
        token_counts = Counter(all_tokens_flat)
        vocab_list = sorted(token_counts.keys())
        self.vocabulary = {word: idx for idx, word in enumerate(vocab_list)}
        vocab_size = len(self.vocabulary)

        if vocab_size == 0:
            return self

        # Step 1: Build co-occurrence matrix
        cooccurrence = [[0.0] * vocab_size for _ in range(vocab_size)]
        total_pairs = 0

        for tokens in all_token_lists:
            for i, token in enumerate(tokens):
                if token not in self.vocabulary:
                    continue
                idx_i = self.vocabulary[token]

                # Look at context window
                start = max(0, i - self.window_size)
                end = min(len(tokens), i + self.window_size + 1)

                for j in range(start, end):
                    if i == j:
                        continue
                    context_token = tokens[j]
                    if context_token not in self.vocabulary:
                        continue
                    idx_j = self.vocabulary[context_token]
                    # Weight by distance (closer words = higher weight)
                    distance = abs(i - j)
                    weight = 1.0 / distance
                    cooccurrence[idx_i][idx_j] += weight
                    total_pairs += weight

        # Step 2: Apply PPMI (Positive Pointwise Mutual Information)
        # PMI(w, c) = log(P(w,c) / (P(w) * P(c)))
        # PPMI = max(0, PMI)
        row_sums = [sum(row) for row in cooccurrence]
        total = sum(row_sums) if sum(row_sums) > 0 else 1.0

        ppmi_matrix = [[0.0] * vocab_size for _ in range(vocab_size)]
        for i in range(vocab_size):
            for j in range(vocab_size):
                if cooccurrence[i][j] == 0:
                    continue
                p_ij = cooccurrence[i][j] / total
                p_i = row_sums[i] / total
                p_j = row_sums[j] / total

                if p_i > 0 and p_j > 0:
                    pmi = math.log(p_ij / (p_i * p_j) + 1e-10)
                    ppmi_matrix[i][j] = max(0.0, pmi)

        # Step 3: Truncated SVD via power iteration
        # This gives us dense vectors of size embedding_dim
        actual_dim = min(self.embedding_dim, vocab_size)
        embeddings = self._power_iteration_svd(ppmi_matrix, actual_dim)

        # Store word vectors
        idx_to_word = {idx: word for word, idx in self.vocabulary.items()}
        self.word_vectors = {}
        for idx in range(vocab_size):
            word = idx_to_word[idx]
            self.word_vectors[word] = l2_normalize(embeddings[idx])

        return self

    def _power_iteration_svd(
        self, matrix: list[list[float]], k: int, n_iter: int = 50
    ) -> list[list[float]]:
        """
        Approximate top-k singular vectors via power iteration.

        For each singular vector:
            1. Start with a random vector
            2. Repeatedly multiply by M^T * M (for right singular vectors)
            3. Normalize after each iteration
            4. Deflate the matrix to find the next vector

        This is equivalent to computing the top-k components of SVD.
        """
        import random
        random.seed(42)

        n = len(matrix)
        if n == 0 or k == 0:
            return [[0.0] * k for _ in range(n)]

        # Compute M^T * M for eigendecomposition
        mtm = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                val = 0.0
                for p in range(n):
                    val += matrix[p][i] * matrix[p][j]
                mtm[i][j] = val

        result_vectors = [[0.0] * k for _ in range(n)]
        current_mtm = [row[:] for row in mtm]  # deep copy

        for component in range(k):
            # Initialize random vector
            v = [random.gauss(0, 1) for _ in range(n)]
            v = l2_normalize(v)

            # Power iteration
            for _ in range(n_iter):
                # Multiply: v_new = M^T*M * v
                v_new = [0.0] * n
                for i in range(n):
                    for j in range(n):
                        v_new[i] += current_mtm[i][j] * v[j]
                v = l2_normalize(v_new)

            # Store this component for each word
            for i in range(n):
                result_vectors[i][component] = v[i]

            # Deflate: remove this component from M^T*M
            eigenvalue = 0.0
            mv = [0.0] * n
            for i in range(n):
                for j in range(n):
                    mv[i] += current_mtm[i][j] * v[j]
                eigenvalue += mv[i] * v[i]

            for i in range(n):
                for j in range(n):
                    current_mtm[i][j] -= eigenvalue * v[i] * v[j]

        return result_vectors

    def embed_text(self, text: str) -> list[float]:
        """
        Embed a text string by averaging its word vectors.

        This is the "bag of embeddings" approach:
            doc_vector = (1/|tokens|) * Σ word_vector(token)

        Returns L2-normalized vector.
        """
        tokens = tokenize(text)
        actual_dim = min(self.embedding_dim, len(self.vocabulary)) if self.vocabulary else self.embedding_dim

        if not tokens or not self.word_vectors:
            return [0.0] * actual_dim

        # Average word vectors
        avg = [0.0] * actual_dim
        count = 0
        for token in tokens:
            if token in self.word_vectors:
                vec = self.word_vectors[token]
                for i in range(len(vec)):
                    avg[i] += vec[i]
                count += 1

        if count > 0:
            avg = [x / count for x in avg]

        return l2_normalize(avg)


# ===========================================================================
#  Retriever implementations using custom embeddings
# ===========================================================================

class TfIdfRetriever:
    """
    Retriever that uses TF-IDF vectors + cosine similarity.

    Workflow:
        1. Fit TF-IDF on all tag descriptions (the "document corpus")
        2. For each query, compute TF-IDF vector
        3. Compute cosine similarity between query and all documents
        4. Return documents sorted by similarity (descending)
    """

    def __init__(self):
        self.vectorizer = TfIdfVectorizer()
        self.doc_vectors: list[list[float]] = []
        self.doc_ids: list[str] = []

    def fit(self, tags: list[dict]) -> "TfIdfRetriever":
        """Index all tags."""
        documents = []
        self.doc_ids = []

        for tag in tags:
            # Combine all tag fields into one document
            doc = f"{tag['label']} {tag['room_name']} {tag['position']} {tag.get('notes', '')}"
            documents.append(doc)
            self.doc_ids.append(tag["id"])

        self.vectorizer.fit(documents)

        # Pre-compute and L2-normalize all document vectors
        self.doc_vectors = [
            self.vectorizer.transform_normalized(doc) for doc in documents
        ]

        return self

    def retrieve(self, query: str) -> list[str]:
        """Retrieve ranked tag IDs for a query."""
        query_vec = self.vectorizer.transform_normalized(query)

        # Compute cosine similarity with all docs
        # Since both vectors are L2-normalized, cosine_sim = dot_product
        similarities = []
        for i, doc_vec in enumerate(self.doc_vectors):
            sim = dot_product(query_vec, doc_vec)
            similarities.append((self.doc_ids[i], sim))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return [doc_id for doc_id, _ in similarities]

    def retrieve_with_scores(self, query: str) -> list[tuple[str, float]]:
        """Retrieve ranked tag IDs with similarity scores."""
        query_vec = self.vectorizer.transform_normalized(query)
        similarities = []
        for i, doc_vec in enumerate(self.doc_vectors):
            sim = dot_product(query_vec, doc_vec)
            similarities.append((self.doc_ids[i], sim))
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities


class BM25Retriever:
    """Retriever using BM25 scoring."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.scorer = BM25Scorer(k1=k1, b=b)

    def fit(self, tags: list[dict]) -> "BM25Retriever":
        documents = []
        doc_ids = []
        for tag in tags:
            doc = f"{tag['label']} {tag['room_name']} {tag['position']} {tag.get('notes', '')}"
            documents.append(doc)
            doc_ids.append(tag["id"])
        self.scorer.fit(documents, doc_ids)
        return self

    def retrieve(self, query: str) -> list[str]:
        return self.scorer.retrieve(query)


class EmbeddingRetriever:
    """
    Retriever using custom co-occurrence embeddings + cosine similarity.

    This is the dense retrieval approach:
        1. Learn word embeddings from the tag corpus via SVD
        2. Embed documents and queries by averaging word vectors
        3. Rank by cosine similarity
    """

    def __init__(self, embedding_dim: int = 32):
        self.embedder = CooccurrenceEmbeddings(embedding_dim=embedding_dim)
        self.doc_vectors: list[list[float]] = []
        self.doc_ids: list[str] = []

    def fit(self, tags: list[dict]) -> "EmbeddingRetriever":
        documents = []
        self.doc_ids = []

        for tag in tags:
            doc = f"{tag['label']} {tag['room_name']} {tag['position']} {tag.get('notes', '')}"
            documents.append(doc)
            self.doc_ids.append(tag["id"])

        self.embedder.fit(documents)

        # Pre-compute document embeddings (already L2-normalized)
        self.doc_vectors = [self.embedder.embed_text(doc) for doc in documents]

        return self

    def retrieve(self, query: str) -> list[str]:
        query_vec = self.embedder.embed_text(query)

        similarities = []
        for i, doc_vec in enumerate(self.doc_vectors):
            sim = dot_product(query_vec, doc_vec)  # both L2-normalized
            similarities.append((self.doc_ids[i], sim))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return [doc_id for doc_id, _ in similarities]

    def retrieve_with_scores(self, query: str) -> list[tuple[str, float]]:
        query_vec = self.embedder.embed_text(query)
        similarities = []
        for i, doc_vec in enumerate(self.doc_vectors):
            sim = dot_product(query_vec, doc_vec)
            similarities.append((self.doc_ids[i], sim))
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities
