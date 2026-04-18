# Legal Document Q&A Engine — Complete Build Roadmap

## Project Codename: **VakilSearch AI** (or pick your own)

**Timeline:** 6 weeks (with 2 weeks buffer for polish)
**Goal:** A production-grade RAG system over Indian legal documents with hybrid retrieval, cross-encoder re-ranking, evaluation metrics, and cited answers.

---

## PART 0: SKILL AUDIT — What You Already Know vs What You Need to Learn

### Things You Already Know (DO NOT waste time relearning)

Based on your GitHub profile and our past conversations:

| Skill | Evidence | Time Saved |
|-------|----------|------------|
| PostgreSQL + schema design | BeEducated has 18 migrations, Prisma in SellWell | Don't redo SQL tutorials |
| Redis + queue systems | ConquerManage (BullMQ), Limitron | Celery is just Python BullMQ — skim docs, don't take a course |
| REST API design | 50+ endpoints in BeEducated | You know routing, middleware, error handling |
| Docker | ConquerManage has docker-compose, you did a 30-video Docker course | Just write the Dockerfile, don't relearn |
| Auth + middleware patterns | Clerk JWT in BeEducated, JWT deep prep in interviews | Skip auth for this project — use API keys or skip it entirely for MVP |
| React + TypeScript frontend | BeEducated, AI-saas | Keep frontend minimal, don't over-invest here |
| Git, deployment, Vercel | Every project | Just deploy, no tutorials needed |

### Things You MUST Learn (These Are Critical and New)

| Concept | Why It Matters | How Long to Learn | Best Resource |
|---------|---------------|-------------------|---------------|
| How embeddings work (not just API calls) | You need to understand vector space, cosine similarity, why some models are better for retrieval vs similarity | 2-3 hours | Read the MTEB leaderboard, then Sentence Transformers docs |
| Chunking strategies | Bad chunking = bad retrieval, no matter how good your model is. This is the #1 failure point in RAG systems | 2 hours | LlamaIndex chunking docs + Greg Kamradt's "5 Levels of Text Splitting" YouTube video |
| pgvector operations | You know PostgreSQL but not vector operations — indexing (IVFFlat vs HNSW), distance functions (cosine vs L2), and query syntax | 1-2 hours | pgvector GitHub README + Supabase pgvector guide |
| Cross-encoder re-ranking | Bi-encoders (embeddings) are fast but rough. Cross-encoders are slow but precise. Understanding WHY you need two stages is key for interviews | 1 hour | Sentence Transformers cross-encoder docs |
| Reciprocal Rank Fusion (RRF) | How to combine scores from two different retrieval systems (vector + keyword) into one ranked list | 30 min | The original RRF paper is 2 pages. Read it. |
| Retrieval evaluation metrics | Precision@K, Recall@K, MRR, NDCG — you need to measure if your retrieval actually works | 1 hour | IR metrics section in any information retrieval textbook or blog |
| FastAPI async patterns | You know Express. FastAPI is similar but async-first with Pydantic validation built in | 2-3 hours | FastAPI official tutorial (it's excellent) |
| Celery basics | Task definition, worker config, result backend | 1 hour | Celery "First Steps" docs |
| PyMuPDF / pdfplumber | PDF text extraction, handling headers/footers, page-level extraction | 1 hour | Just read the quickstart for each |
| Prompt engineering for RAG | How to structure the prompt with retrieved context so the LLM cites properly and doesn't hallucinate | 1 hour | Anthropic's prompt engineering guide (you've used Claude enough to get this fast) |

**Total new learning: ~15-18 hours spread across the first 2 weeks.**

---

## PART 1: ARCHITECTURE DECISIONS (Read Before Coding)

### Why Each Component Exists

```
User Query
    │
    ▼
┌─────────────────────────┐
│  Query Processing        │  ← Clean the query, expand if needed
└──────────┬──────────────┘
           │
     ┌─────┴──────┐
     ▼            ▼
┌─────────┐  ┌──────────┐
│ Vector  │  │ Keyword  │   ← TWO separate retrieval paths
│ Search  │  │ Search   │     Vector catches semantic meaning ("What is the punishment for theft?")
│(pgvector)│ │(tsvector)│     Keyword catches exact terms ("Section 378 IPC")
└────┬────┘  └────┬─────┘     Legal docs NEED both — a lawyer searches by section number, not meaning
     │            │
     └─────┬──────┘
           ▼
┌─────────────────────────┐
│  Reciprocal Rank Fusion  │  ← Combines both ranked lists into one
│  (RRF)                   │    Score = Σ 1/(k + rank_i) for each system
└──────────┬──────────────┘    k=60 is standard. Simple formula, powerful results.
           │
           ▼
┌─────────────────────────┐
│  Cross-Encoder Reranker  │  ← Takes top 20 candidates, re-scores each pair (query, chunk)
│  (ms-marco-MiniLM)      │    This is SLOW (processes each pair individually) but PRECISE
└──────────┬──────────────┘    Why not use this for everything? 20 pairs = fine. 10,000 pairs = minutes.
           │                   That's why we have the fast first stage.
           ▼
┌─────────────────────────┐
│  LLM Generation          │  ← Takes top 5 chunks + original query
│  (Groq / Llama 3.1)     │    Generates answer WITH citations pointing to source chunks
└──────────┬──────────────┘    Citation = chunk_id + page_number + document_name
           │
           ▼
┌─────────────────────────┐
│  Response + Citations    │  ← User sees: answer text + "Source: Document X, Page Y, Paragraph Z"
└─────────────────────────┘
```

### Why Hybrid Search (Not Just Vector)?

Legal documents have a unique property: lawyers search by BOTH meaning AND exact references.

- "What are the rights of a tenant?" → Semantic search works great
- "Section 24 of Hindu Marriage Act" → Vector search will return random sections about marriage. Keyword search nails it.
- "Maintenance under CrPC 125" → You need BOTH — the meaning of maintenance AND the exact section number

If you only build vector search, you fail on exact references. If you only build keyword search, you fail on conceptual queries. Hybrid search with RRF handles both. This is the #1 thing that makes your project non-trivial.

### Why Re-ranking?

Bi-encoder embeddings (what pgvector uses) encode the query and each chunk INDEPENDENTLY, then compare. This is fast but lossy — it can't model fine-grained interactions between query and chunk words.

Cross-encoders take (query, chunk) as a SINGLE input and output a relevance score. They see both together, so they catch nuances like negation, specific references, and context that bi-encoders miss.

The tradeoff: cross-encoders are 100x slower. So you use bi-encoders to get top 20-30 candidates fast, then re-rank with cross-encoder to get the best 5. This two-stage approach is industry standard at companies like Google, Cohere, and every serious RAG system.

### Database Schema (Design This Before Writing Code)

```sql
-- Documents table: stores metadata about uploaded PDFs
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    file_path TEXT NOT NULL,           -- S3/Supabase storage path
    file_hash TEXT NOT NULL UNIQUE,    -- SHA256 to prevent duplicate uploads
    total_pages INTEGER,
    total_chunks INTEGER,
    document_type TEXT DEFAULT 'legal', -- legal, medical, general
    processing_status TEXT DEFAULT 'pending', -- pending, processing, completed, failed
    processing_error TEXT,
    metadata JSONB DEFAULT '{}',       -- flexible: court name, case number, date, parties
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chunks table: stores text chunks with their embeddings
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,       -- order within document
    content TEXT NOT NULL,              -- the actual chunk text
    page_number INTEGER,               -- which page this came from
    section_header TEXT,                -- detected section/heading if any
    chunk_type TEXT DEFAULT 'text',     -- text, table, header, footer
    token_count INTEGER,
    embedding vector(384),             -- dimension depends on model (MiniLM=384, BGE=768)
    metadata JSONB DEFAULT '{}',       -- paragraph number, formatting info
    created_at TIMESTAMPTZ DEFAULT NOW(),

    -- Full-text search column
    content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);

-- Indexes for performance
CREATE INDEX idx_chunks_document_id ON chunks(document_id);
CREATE INDEX idx_chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_chunks_content_tsv ON chunks USING gin(content_tsv);

-- Query history for evaluation
CREATE TABLE queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_text TEXT NOT NULL,
    response_text TEXT,
    retrieved_chunk_ids UUID[],        -- which chunks were retrieved
    reranked_chunk_ids UUID[],         -- which chunks survived reranking
    model_used TEXT,
    retrieval_latency_ms INTEGER,
    generation_latency_ms INTEGER,
    total_latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Evaluation ground truth (you'll build this manually for ~50-100 queries)
CREATE TABLE evaluation_pairs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_text TEXT NOT NULL,
    relevant_chunk_ids UUID[] NOT NULL, -- manually labeled correct chunks
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Project Structure (Set This Up on Day 1)

```
legal-qa-engine/
├── docker-compose.yml           # PostgreSQL + Redis + pgvector
├── Dockerfile
├── requirements.txt
├── .env.example
├── README.md
│
├── app/
│   ├── main.py                  # FastAPI app entry
│   ├── config.py                # Settings, env vars (Pydantic BaseSettings)
│   ├── dependencies.py          # DB session, Redis connection
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── documents.py     # Upload, list, delete documents
│   │   │   ├── query.py         # Ask questions, get answers
│   │   │   ├── evaluation.py    # Run eval, get metrics
│   │   │   └── health.py        # Health check
│   │   └── schemas/
│   │       ├── documents.py     # Pydantic request/response models
│   │       ├── query.py
│   │       └── evaluation.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── chunker.py           # Text splitting strategies
│   │   ├── embedder.py          # Embedding generation (Sentence Transformers)
│   │   ├── retriever.py         # Hybrid search (vector + keyword + RRF)
│   │   ├── reranker.py          # Cross-encoder reranking
│   │   ├── generator.py         # LLM call with prompt template
│   │   ├── parser.py            # PDF parsing (PyMuPDF + pdfplumber)
│   │   └── evaluator.py         # Precision@K, Recall@K, MRR calculation
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py           # AsyncPG / SQLAlchemy async session
│   │   ├── models.py            # SQLAlchemy models
│   │   └── migrations/          # Alembic migrations
│   │
│   └── workers/
│       ├── __init__.py
│       └── tasks.py             # Celery tasks: parse PDF, chunk, embed, store
│
├── tests/
│   ├── test_chunker.py
│   ├── test_retriever.py
│   ├── test_reranker.py
│   └── test_evaluator.py
│
├── eval/
│   ├── ground_truth.json        # Your manually labeled query-chunk pairs
│   └── run_eval.py              # Script to run full evaluation suite
│
├── scripts/
│   ├── seed_documents.py        # Download and ingest sample legal docs
│   └── create_eval_set.py       # Helper to create evaluation pairs
│
└── frontend/                    # React app (add in week 5)
    ├── src/
    │   ├── App.tsx
    │   ├── components/
    │   │   ├── SearchBar.tsx
    │   │   ├── AnswerCard.tsx
    │   │   ├── CitationList.tsx
    │   │   ├── DocumentUpload.tsx
    │   │   └── MetricsDashboard.tsx
    │   └── api/
    │       └── client.ts
    └── package.json
```

---

## PART 2: WEEK-BY-WEEK BUILD PLAN

---

## WEEK 1: Foundation — Parser, Chunker, and Database

**Goal:** By end of week, you can upload a legal PDF and see it parsed, chunked, and stored in PostgreSQL with full-text search working.

### Day 1 (Monday): Environment Setup + FastAPI Skeleton

**Morning (2-3 hours):**
- Create GitHub repo with the project structure above
- Set up Python virtual environment (use Python 3.11+)
- Create `requirements.txt`:
  ```
  fastapi==0.115.0
  uvicorn[standard]==0.30.0
  sqlalchemy[asyncio]==2.0.35
  asyncpg==0.29.0
  alembic==1.13.0
  celery[redis]==5.4.0
  redis==5.1.0
  python-multipart==0.0.9
  pydantic-settings==2.5.0
  pymupdf==1.24.0
  pdfplumber==0.11.0
  sentence-transformers==3.1.0
  pgvector==0.3.0
  httpx==0.27.0
  python-dotenv==1.0.0
  ```
- Write `docker-compose.yml` with:
  - PostgreSQL 16 with pgvector extension (`ankane/pgvector:latest`)
  - Redis 7
- Write `app/main.py` — basic FastAPI app with health check endpoint
- Write `app/config.py` — Pydantic BaseSettings loading from .env
- Test: `docker compose up`, `uvicorn app.main:app --reload`, hit `/health`

**Afternoon (2-3 hours):**
- Write `app/db/models.py` — SQLAlchemy models for documents, chunks, queries tables
- Set up Alembic for migrations: `alembic init app/db/migrations`
- Create first migration with the schema from Part 1
- Run migration, verify tables exist in PostgreSQL
- Write `app/api/routes/documents.py` — POST `/documents/upload` endpoint (just accepts file, saves metadata, returns document_id. No processing yet.)
- Test: Upload a PDF via curl/Postman, see it in the documents table

**What to learn today:** If you haven't used FastAPI before, spend the first 30 minutes on the official tutorial's "First Steps" and "Path Parameters" sections. It's Express but with type hints and auto-validation.

**Common mistake:** Don't try to use Supabase's hosted PostgreSQL yet. Develop locally with Docker. Supabase's free tier has connection limits that will annoy you during development. Deploy to Supabase later.

### Day 2 (Tuesday): PDF Parser

**Morning (3 hours):**
- **Learn first:** Open 3-4 Indian legal PDFs (download from Indian Kanoon — https://indiankanoon.org). Look at the structure. Notice: they have headers/footers on every page, page numbers, section numbering, citations in brackets, judge names, court names. Your parser needs to handle this.
- Write `app/core/parser.py`:
  - Function `parse_pdf(file_path: str) -> list[dict]` that returns a list of `{page_number, text, tables}` per page
  - Use PyMuPDF (`fitz`) as primary parser
  - Strip headers/footers (they repeat on every page and will pollute your chunks)
  - Handle encoding issues (Indian legal PDFs sometimes have weird Unicode)
  - Extract metadata: try to detect case title, court name, date from the first page

**Afternoon (2 hours):**
- Write tests for the parser: `tests/test_parser.py`
  - Test with a clean PDF
  - Test with a scanned PDF (should return empty or minimal text — log a warning)
  - Test with a multi-column PDF
- Add pdfplumber as fallback for PDFs where PyMuPDF returns garbled text (some legal PDFs have weird font encodings that PyMuPDF handles poorly but pdfplumber manages)

**Expected output:** You can run `parse_pdf("some_legal_doc.pdf")` and get clean, page-numbered text back.

**Common mistake:** Not stripping headers/footers. If your PDF has "HIGH COURT OF DELHI" on every page, that phrase will appear in 50% of your chunks and completely destroy retrieval quality. Detect repeating text across pages and strip it.

### Day 3 (Wednesday): Chunking Engine

**Morning — Learn first (1 hour):**
Watch Greg Kamradt's "5 Levels of Text Splitting" (YouTube, ~20 min). Then read about:
- Fixed-size chunking (split every N tokens) — simple but cuts sentences/paragraphs mid-thought
- Recursive character splitting — splits on \n\n, then \n, then sentences, then words
- Semantic chunking — embeds sentences, groups consecutive sentences with high similarity

For legal documents, you want **recursive splitting with section-awareness**: try to split on section boundaries (numbered sections, headings) first, then fall back to paragraph boundaries, then sentences.

**Afternoon (3-4 hours):**
- Write `app/core/chunker.py`:
  ```python
  class ChunkingConfig:
      chunk_size: int = 512        # tokens
      chunk_overlap: int = 50      # tokens overlap between consecutive chunks
      min_chunk_size: int = 100    # don't create tiny chunks
  
  def chunk_document(pages: list[dict], config: ChunkingConfig) -> list[dict]:
      """
      Returns list of {content, page_number, chunk_index, section_header, token_count}
      """
  ```
- Implement section-aware splitting:
  1. First, try to split on section headers (detect patterns like "Section 1.", "1.", "ARTICLE I", "ORDER XII")
  2. Within each section, split on paragraph boundaries (\n\n)
  3. If a paragraph exceeds chunk_size, split on sentence boundaries
  4. Add overlap between consecutive chunks (last 50 tokens of chunk N become first 50 tokens of chunk N+1)
- Track which page each chunk came from
- Track section headers if detected
- Count tokens using a simple tokenizer (tiktoken `cl100k_base` or just `len(text.split())` as approximation)

**Write tests:**
- Chunk a short document, verify no chunks exceed max size
- Verify overlap exists between consecutive chunks
- Verify page numbers are correctly tracked
- Verify section headers are detected

**Expected output:** A legal PDF gets split into ~50-200 chunks of ~512 tokens each, with page numbers and section headers preserved.

**Common mistake:** Chunks that are too small (100 tokens) lose context. Chunks that are too large (2000 tokens) are vague and hurt retrieval precision. 512 tokens with 50-token overlap is a good default. You can experiment later.

### Day 4 (Thursday): Embedding Pipeline

**Morning — Learn first (1 hour):**
- Read Sentence Transformers quickstart
- Understand: an embedding model converts text → a fixed-size vector (array of floats). Similar texts have vectors that are close together (high cosine similarity). You encode ONCE and store. At query time, you encode the query and find the closest stored vectors.
- `all-MiniLM-L6-v2` outputs 384-dimensional vectors. Fast, decent quality.
- `BAAI/bge-base-en-v1.5` outputs 768-dimensional vectors. Slower, better quality for retrieval.
- Start with MiniLM for speed. Switch to BGE when your pipeline works.

**Afternoon (3 hours):**
- Write `app/core/embedder.py`:
  ```python
  from sentence_transformers import SentenceTransformer
  
  class Embedder:
      def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
          self.model = SentenceTransformer(model_name)
          self.dimension = self.model.get_sentence_embedding_dimension()
      
      def embed_texts(self, texts: list[str]) -> list[list[float]]:
          """Batch embed multiple texts. Returns list of vectors."""
          embeddings = self.model.encode(texts, show_progress_bar=True, batch_size=32)
          return embeddings.tolist()
      
      def embed_query(self, query: str) -> list[float]:
          """Embed a single query. Some models need different prefixes for queries vs documents."""
          return self.model.encode(query).tolist()
  ```
- **Important:** Some models (like BGE) need a prefix for queries: `"Represent this sentence for searching relevant passages: " + query`. MiniLM doesn't need this. Handle this in your Embedder class based on model name.
- Update your `chunks` table: make sure the `embedding` column dimension matches your model (384 for MiniLM, 768 for BGE)
- Write a function that takes chunks → generates embeddings → inserts into PostgreSQL with pgvector
- Test: embed 10 chunks, store them, run a simple cosine similarity query to verify it works

**Common mistake:** Not batching embeddings. Embedding one text at a time is 10x slower than batching 32 at a time. Always use `batch_size=32` in `model.encode()`.

### Day 5 (Friday): Celery Worker + Full Ingestion Pipeline

**Morning (2 hours):**
- Set up Celery with Redis broker:
  ```python
  # app/workers/tasks.py
  from celery import Celery
  
  celery_app = Celery("legal_qa", broker="redis://localhost:6379/0")
  
  @celery_app.task
  def process_document(document_id: str):
      """
      Full pipeline:
      1. Fetch document record from DB
      2. Download PDF from storage
      3. Parse PDF → pages
      4. Chunk pages → chunks
      5. Generate embeddings for all chunks
      6. Store chunks + embeddings in DB
      7. Update document status to 'completed'
      """
  ```
- Wire it up: when POST `/documents/upload` is called, save the file, create document record, dispatch Celery task

**Afternoon (3 hours):**
- Implement the full `process_document` task with proper error handling:
  - If parsing fails → set status to 'failed' with error message
  - If embedding fails → same
  - Update progress (optional: store in Redis so frontend can poll)
- Test the complete flow:
  1. Upload a PDF via API
  2. See Celery worker pick it up in logs
  3. Watch chunks appear in the database
  4. Query pgvector to verify embeddings are stored
- Upload 3-5 Indian legal documents (download from Indian Kanoon)

**Expected output at end of Week 1:**
- You can upload legal PDFs via API
- They get parsed, chunked, embedded, and stored asynchronously
- You can see chunks in PostgreSQL with embeddings
- A raw pgvector similarity query returns relevant chunks for a test query

### Day 6-7 (Weekend): Buffer + Documentation

- Write README with setup instructions
- Fix any bugs from the week
- Download and ingest 15-20 legal documents to have a decent corpus
- If ahead of schedule: start reading about full-text search in PostgreSQL

---

## WEEK 2: Retrieval Engine — Hybrid Search + Reranking

**Goal:** By end of week, you have a working query endpoint that does hybrid search, RRF fusion, and cross-encoder reranking, returning cited chunks.

### Day 8 (Monday): Vector Search Module

**Morning (2 hours):**
- Write `app/core/retriever.py` — start with vector-only search:
  ```python
  async def vector_search(query_embedding: list[float], top_k: int = 20) -> list[dict]:
      """
      Uses pgvector to find top_k most similar chunks.
      Returns: [{chunk_id, content, score, page_number, document_title, section_header}]
      """
      # SQL: SELECT *, 1 - (embedding <=> query_embedding) as score 
      #      FROM chunks ORDER BY embedding <=> query_embedding LIMIT top_k
  ```
- Note: `<=>` is cosine distance in pgvector. `1 - distance = similarity`. Higher is better.
- Test with 5 different queries, manually check if results make sense

**Afternoon (2 hours):**
- Experiment with `top_k` values: try 10, 20, 50. See how quality changes.
- Add filtering: allow searching within a specific document or document type
- Profile the query latency. pgvector with HNSW index should return in <50ms for ~10k chunks.

### Day 9 (Tuesday): Keyword Search + Hybrid Fusion

**Morning — Learn first (30 min):**
- PostgreSQL full-text search: `to_tsvector('english', text)` creates a searchable representation. `to_tsquery('english', query)` creates a search query. `ts_rank()` scores relevance.
- Read: https://www.postgresql.org/docs/current/textsearch.html (just the intro and ranking sections)

**Morning continued (2 hours):**
- Add keyword search to `retriever.py`:
  ```python
  async def keyword_search(query: str, top_k: int = 20) -> list[dict]:
      """
      Uses PostgreSQL full-text search.
      Handles legal-specific terms: "Section 302", "IPC", "CrPC" etc.
      """
      # Convert query to tsquery
      # SQL: SELECT *, ts_rank(content_tsv, query) as score
      #      FROM chunks WHERE content_tsv @@ to_tsquery('english', query)
      #      ORDER BY score DESC LIMIT top_k
  ```

**Afternoon (3 hours):**
- Implement Reciprocal Rank Fusion (RRF):
  ```python
  def reciprocal_rank_fusion(
      vector_results: list[dict], 
      keyword_results: list[dict], 
      k: int = 60
  ) -> list[dict]:
      """
      Combines two ranked lists using RRF.
      For each chunk, score = sum of 1/(k + rank) across all lists it appears in.
      k=60 is the standard constant from the original paper.
      """
      scores = {}
      for rank, result in enumerate(vector_results):
          chunk_id = result["chunk_id"]
          scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (k + rank + 1)
      
      for rank, result in enumerate(keyword_results):
          chunk_id = result["chunk_id"]
          scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (k + rank + 1)
      
      # Sort by combined score, return top results
      # Merge metadata from both result sets
  ```
- Write the combined `hybrid_search()` function that calls both, fuses with RRF, returns top 20
- Test: compare vector-only vs keyword-only vs hybrid for queries like:
  - "What is the punishment for murder?" (semantic — vector should win)
  - "Section 302 IPC" (exact — keyword should win)
  - "Bail provisions under Section 439 CrPC" (needs both)

**Expected output:** Hybrid search returns better results than either method alone for mixed queries.

**Common mistake:** Not normalizing scores before RRF. Vector similarity is 0-1, ts_rank can be arbitrary. RRF handles this naturally because it uses RANKS not scores. That's the beauty of it.

### Day 10 (Wednesday): Cross-Encoder Reranker

**Morning — Learn first (30 min):**
- Cross-encoders take (query, passage) as input and output a relevance score from 0-1
- Unlike bi-encoders (embeddings), they see both texts together — much more accurate
- `cross-encoder/ms-marco-MiniLM-L-6-v2` is trained on MS MARCO passage ranking dataset — perfect for document retrieval

**Morning continued + Afternoon (3-4 hours):**
- Write `app/core/reranker.py`:
  ```python
  from sentence_transformers import CrossEncoder
  
  class Reranker:
      def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
          self.model = CrossEncoder(model_name)
      
      def rerank(self, query: str, chunks: list[dict], top_k: int = 5) -> list[dict]:
          """
          Takes query + candidate chunks, re-scores with cross-encoder.
          Returns top_k chunks sorted by cross-encoder score.
          """
          pairs = [(query, chunk["content"]) for chunk in chunks]
          scores = self.model.predict(pairs)
          
          for chunk, score in zip(chunks, scores):
              chunk["rerank_score"] = float(score)
          
          reranked = sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)
          return reranked[:top_k]
  ```
- Integrate into the pipeline: hybrid_search(top_k=20) → rerank(top_k=5)
- Test: measure how much reranking changes the order. For good queries, the top result often stays but positions 2-5 shuffle significantly.
- **Profile latency:** Reranking 20 chunks should take 100-300ms. If it's slower, reduce to top 15.

### Day 11 (Thursday): Query Endpoint + LLM Generation

**Morning (2 hours):**
- Write `app/core/generator.py`:
  ```python
  import httpx
  
  class Generator:
      def __init__(self, api_key: str, model: str = "llama-3.1-70b-versatile"):
          self.api_key = api_key
          self.model = model
          self.base_url = "https://api.groq.com/openai/v1"
      
      async def generate_answer(self, query: str, chunks: list[dict]) -> dict:
          """
          Sends query + retrieved chunks to Groq LLM.
          Returns: {answer: str, citations: [{chunk_id, page_number, document}]}
          """
          context = self._format_context(chunks)
          prompt = self._build_prompt(query, context)
          
          # Call Groq API (OpenAI-compatible)
          # Parse response, extract citations
  ```
- **Critical — the prompt template matters enormously:**
  ```
  You are a legal research assistant. Answer the question using ONLY the provided context.
  
  Rules:
  1. If the answer is not in the context, say "I cannot find this information in the provided documents."
  2. Cite your sources using [Source X] format, where X is the source number.
  3. Be precise. Quote relevant legal provisions directly.
  4. If multiple sources are relevant, cite all of them.
  
  Context:
  [Source 1] (Document: {doc_title}, Page: {page_num})
  {chunk_content}
  
  [Source 2] (Document: {doc_title}, Page: {page_num})
  {chunk_content}
  
  ... (up to 5 sources)
  
  Question: {query}
  
  Answer:
  ```

**Afternoon (3 hours):**
- Write `app/api/routes/query.py`:
  ```python
  @router.post("/query")
  async def ask_question(request: QueryRequest):
      """
      Full pipeline:
      1. Embed query
      2. Hybrid search (vector + keyword + RRF)
      3. Rerank top 20 → top 5
      4. Generate answer with citations
      5. Log query + latencies to queries table
      6. Return answer + sources + metrics
      """
  ```
- Log everything: retrieval latency, reranking latency, generation latency, total latency
- Return response format:
  ```json
  {
    "answer": "Under Section 302 of the IPC, the punishment for murder is...",
    "citations": [
      {"source_number": 1, "document": "IPC.pdf", "page": 45, "chunk_preview": "Section 302..."},
      {"source_number": 2, "document": "CrPC_Commentary.pdf", "page": 120, "chunk_preview": "..."}
    ],
    "metrics": {
      "retrieval_ms": 85,
      "reranking_ms": 210,
      "generation_ms": 1200,
      "total_ms": 1495,
      "chunks_retrieved": 20,
      "chunks_after_rerank": 5
    }
  }
  ```

### Day 12 (Friday): Testing + Latency Optimization

- Test the full pipeline end-to-end with 20 different queries
- Identify slow queries and understand why (bad chunks? slow embedding? large context?)
- Add connection pooling for database (asyncpg pool)
- Cache embeddings model in memory (load once, reuse)
- Cache frequently asked queries in Redis (TTL 1 hour)
- Verify Groq rate limits — free tier is 30 RPM for Llama 70B. Add rate limiting to your query endpoint.

### Day 13-14 (Weekend): Buffer + Ingest More Documents

- Fix bugs from the week
- Ingest 30-50 legal documents total (Indian Kanoon has thousands — pick landmark cases from different areas: criminal, civil, property, family law)
- Manually test 20-30 queries and note which ones fail — this becomes your evaluation set

**Expected output at end of Week 2:**
- Complete query pipeline: upload → ask → get cited answer
- Hybrid search with RRF fusion working
- Cross-encoder reranking working
- Full latency logging
- 30-50 documents ingested

---

## WEEK 3: Evaluation Framework + Quality Improvements

**Goal:** Build a proper evaluation system so you can measure and improve retrieval quality with real numbers.

### Tasks:

**Build the evaluation dataset (2 days):**
- Manually create 50-100 (query, relevant_chunks) pairs
- For each query, note which chunks actually answer it (do this by reading the chunks yourself)
- Store in `evaluation_pairs` table and as `eval/ground_truth.json`
- This is tedious but ESSENTIAL. Without this, you're guessing about quality.

**Write the evaluator (1 day):**
- `app/core/evaluator.py`:
  ```python
  def precision_at_k(retrieved_ids: list, relevant_ids: list, k: int) -> float:
      """Of the top K retrieved chunks, how many are actually relevant?"""
      top_k = retrieved_ids[:k]
      relevant_in_top_k = len(set(top_k) & set(relevant_ids))
      return relevant_in_top_k / k
  
  def recall_at_k(retrieved_ids: list, relevant_ids: list, k: int) -> float:
      """Of all relevant chunks, how many did we find in top K?"""
      top_k = retrieved_ids[:k]
      relevant_in_top_k = len(set(top_k) & set(relevant_ids))
      return relevant_in_top_k / len(relevant_ids) if relevant_ids else 0
  
  def mrr(retrieved_ids: list, relevant_ids: list) -> float:
      """Mean Reciprocal Rank — how early does the first relevant chunk appear?"""
      for rank, chunk_id in enumerate(retrieved_ids):
          if chunk_id in relevant_ids:
              return 1 / (rank + 1)
      return 0
  ```
- Build `/evaluation/run` endpoint that runs all queries through the pipeline and returns aggregate metrics

**Run experiments and improve (2 days):**
- Run eval on: vector-only → keyword-only → hybrid → hybrid+rerank
- You should see improvement at each stage. Document the numbers:
  - Vector only: Precision@5 = X%, MRR = Y
  - Hybrid (RRF): Precision@5 = X+A%, MRR = Y+B
  - Hybrid + Rerank: Precision@5 = X+A+C%, MRR = Y+B+D
- If numbers are bad, debug:
  - Bad chunking? → Try different chunk sizes (256, 512, 1024)
  - Bad embeddings? → Switch from MiniLM to BGE-base
  - Keyword search not matching? → Check your tsquery conversion, maybe add legal term synonyms

**Expected output at end of Week 3:**
- 50-100 manually labeled evaluation pairs
- Evaluation endpoint returning Precision@5, Recall@5, MRR
- Documented improvement from each pipeline stage (this becomes resume material)
- Identified and fixed at least 2-3 quality issues

---

## WEEK 4: Advanced Features + Robustness

**Goal:** Add features that separate this from a tutorial project.

### Tasks:

**Chunk metadata enrichment (1 day):**
- Extract section numbers and hierarchy from legal docs
- Tag chunks with their legal category (criminal, civil, constitutional, etc.) using simple keyword matching
- Add this metadata to the search filter (user can restrict search to criminal law only)

**Query expansion / preprocessing (1 day):**
- Legal query normalization: "Sec. 302" → "Section 302", "IPC" → "Indian Penal Code"
- Query classification: detect if query is factual ("what is"), comparative ("difference between"), or procedural ("how to file")
- For vague queries, use the LLM to expand: "bail" → "bail provisions, conditions for bail, bail under CrPC Section 439"

**Streaming responses (1 day):**
- Add SSE (Server-Sent Events) to stream the LLM response token by token
- FastAPI supports this with `StreamingResponse`
- This makes the UX feel fast even though generation takes 2-3 seconds

**Error handling + edge cases (1 day):**
- Empty query → helpful error message
- Query with no relevant results → "No relevant information found" with suggestions
- PDF that fails parsing → proper error status + retry mechanism
- Rate limiting on query endpoint
- Request timeout handling (Groq sometimes takes 5+ seconds)

**API documentation (1 day):**
- FastAPI generates OpenAPI docs automatically at `/docs`
- Add proper descriptions, examples, and response models to all endpoints
- Write a Postman collection or curl examples in README

**Expected output at end of Week 4:**
- Query preprocessing with legal term normalization
- Streaming responses
- Robust error handling
- Complete API documentation
- Metrics showing improvement from query expansion

---

## WEEK 5: Frontend + Demo Polish

**Goal:** Build a clean frontend that makes the project demo-able.

### Tasks:

**React frontend (3 days):**
- Search bar with typeahead/suggestions
- Results page showing: answer with inline citations, expandable source cards showing the original chunk text + page number + document name
- Document upload page with processing status indicator
- Metrics dashboard showing: average latency, queries per day, retrieval quality scores
- Dark mode (it's 2026, no excuse)

**Keep it simple.** The frontend is NOT the star. Don't spend 3 days on animations. A clean, functional UI with good typography is enough.

**Docker production build (1 day):**
- Multi-stage Dockerfile for FastAPI
- Docker Compose with all services: FastAPI, Celery worker, PostgreSQL+pgvector, Redis
- One command to spin everything up: `docker compose up`

**Deploy (1 day):**
- Frontend → Vercel (you know this)
- Backend → EC2 with Docker (or Railway if you want easier)
- Database → Supabase (enable pgvector extension) or keep on EC2 with Docker
- Redis → Upstash free tier or Docker on EC2

**Expected output at end of Week 5:**
- Working deployed app with public URL
- Clean demo-able frontend
- Docker setup for local development

---

## WEEK 6: Documentation, README, and Resume Optimization

**Goal:** Make this project recruiter-ready and interview-ready.

### Tasks:

**Write a killer README (1 day):**
Structure it EXACTLY like your BeEducated README (which is actually good) but with these sections:
- What it does (2 sentences)
- Architecture diagram (ASCII art showing the full pipeline)
- Why each component (explain chunking, embedding, hybrid search, reranking — shows you UNDERSTAND, not just implemented)
- Tech stack table with "Why" column
- Evaluation results table (Precision@5, Recall@5, MRR for each pipeline stage)
- Latency breakdown (average retrieval, reranking, generation, total)
- How to run (Docker one-command)
- API docs link
- Screenshots/GIF of the UI

**Write ARCHITECTURE.md (1 day):**
- Deep dive into every design decision
- Why hybrid search over vector-only
- Why cross-encoder reranking
- Why RRF over simple score combination
- Chunking strategy and why 512 tokens
- How citations work
- Database schema design rationale
- Scaling considerations (what would you change at 1M documents?)

**Record a demo video (0.5 day):**
- 2-3 minute screencast showing: upload document → ask question → get cited answer
- Show the metrics dashboard
- Post on LinkedIn and Twitter

**Prepare interview talking points (0.5 day):**
Write answers to these questions (you WILL be asked):
1. "Why hybrid search instead of just vector search?"
2. "What's the difference between bi-encoder and cross-encoder?"
3. "How do you evaluate retrieval quality?"
4. "What would you change for 1 million documents?"
5. "Why pgvector over Pinecone?"
6. "How does your chunking strategy handle legal document structure?"
7. "What was the hardest bug you encountered?"

---

## PART 3: METRICS TO TRACK

### Retrieval Quality Metrics (Measure Weekly)

| Metric | What It Means | Target |
|--------|--------------|--------|
| Precision@5 | Of top 5 returned chunks, how many are relevant? | >70% |
| Recall@5 | Of all relevant chunks in the corpus, how many are in top 5? | >60% |
| MRR (Mean Reciprocal Rank) | On average, what position is the first relevant chunk? | >0.7 (meaning first relevant chunk is usually in top 2) |
| NDCG@5 | Quality-weighted ranking metric | >0.65 |

### Latency Metrics (Track Per Query)

| Metric | Target |
|--------|--------|
| Embedding generation | <50ms |
| Vector search (pgvector) | <100ms |
| Keyword search (tsvector) | <50ms |
| RRF fusion | <5ms |
| Cross-encoder reranking (20 chunks) | <300ms |
| LLM generation (Groq) | <3000ms |
| **Total end-to-end** | **<4 seconds** |

### System Metrics

| Metric | How to Track |
|--------|-------------|
| Documents ingested | Count in DB |
| Total chunks | Count in DB |
| Average chunks per document | Simple query |
| Ingestion time per document | Log in Celery task |
| Query volume | Count in queries table |

---

## PART 4: COMMON MISTAKES AND HOW TO AVOID THEM

| Mistake | Why It Happens | How to Avoid |
|---------|---------------|--------------|
| Chunks too small (50-100 tokens) | Feels like "more chunks = better retrieval" | Minimum 256 tokens. Legal paragraphs need context. |
| Not stripping PDF headers/footers | They look like normal text to the parser | Detect repeating text across pages, strip before chunking |
| Using OpenAI embeddings API in a loop | Costs add up fast, rate limits hit | Use local Sentence Transformers. Zero cost, no rate limits. |
| Not evaluating retrieval separately from generation | "The answer is wrong" — but is it retrieval or LLM? | Build eval that tests retrieval alone (Precision@K) before adding LLM |
| Putting all logic in route handlers | FastAPI routes become 200-line monsters | Service layer pattern: routes call core modules |
| Not logging latencies | Can't optimize what you can't measure | Log every stage from day 1 |
| Skipping the evaluation dataset | "I'll evaluate later" → you never do | Build it in Week 3. 50 pairs minimum. |
| Over-engineering the frontend | 2 weeks on React animations, 0 weeks on retrieval quality | Frontend is a thin layer. Spend 3 days max. |
| Not handling Groq rate limits | Free tier = 30 RPM. Hit it during demo. | Add rate limiting + queue + retry logic |
| Using the same embedding model for query and document without prefixes | BGE needs "Represent this sentence..." prefix for queries | Read your embedding model's documentation. Each model is different. |

---

## PART 5: RESUME BULLET POINTS

After completing this project, these are the bullet points you can put on your resume. Each one maps to a specific thing you built:

1. **"Built a domain-specific RAG system for Indian legal documents with hybrid retrieval combining pgvector semantic search and PostgreSQL full-text search, fused via Reciprocal Rank Fusion (RRF)"**
   → Maps to: Week 2, hybrid search implementation

2. **"Implemented two-stage retrieval with cross-encoder re-ranking (ms-marco-MiniLM), improving Precision@5 from X% to Y% over vector-only baseline"**
   → Maps to: Week 2-3, reranker + evaluation. Fill in real numbers.

3. **"Designed a section-aware chunking strategy for legal PDFs preserving section boundaries, page references, and hierarchical structure across 50+ documents"**
   → Maps to: Week 1, chunker

4. **"Built a custom evaluation framework measuring Precision@K, Recall@K, and MRR across 100 manually-labeled query-document pairs, enabling data-driven pipeline optimization"**
   → Maps to: Week 3, evaluation system

5. **"Engineered an async document ingestion pipeline using Celery + Redis processing PDFs through parsing, chunking, and embedding generation with progress tracking and failure recovery"**
   → Maps to: Week 1, Celery pipeline

6. **"Reduced end-to-end query latency to under 4 seconds through HNSW indexing, connection pooling, model caching, and Redis query caching"**
   → Maps to: Week 2 + Week 4 optimizations

7. **"Deployed on AWS EC2 with Docker Compose orchestrating FastAPI, Celery workers, PostgreSQL with pgvector, and Redis"**
   → Maps to: Week 5, deployment

---

## PART 6: WHAT TO DO IF YOU'RE BEHIND SCHEDULE

**If Week 2 ends and retrieval isn't working:**
- Drop query expansion (Week 4) and streaming (Week 4)
- Focus entirely on getting hybrid search + reranking working and measured
- A working pipeline with evaluation numbers > a feature-rich pipeline that's unmeasured

**If Week 4 ends and you have no frontend:**
- Use Streamlit. Seriously. It takes 2 hours to build a functional UI.
- A Streamlit demo with great backend > a polished React app with mediocre retrieval

**The non-negotiables (do NOT skip these):**
1. Hybrid search (vector + keyword + RRF) — this is the core differentiator
2. Cross-encoder reranking — this is what makes it non-trivial
3. Evaluation with real numbers — this is what makes it credible
4. Good README with architecture diagram — this is what recruiters actually read

**Everything else is nice-to-have.**

---

*Last updated: April 2026*
*Estimated total build time: 150-200 hours across 6 weeks*
*Expected outcome: A portfolio project that directly maps to RAG engineer / AI engineer job requirements*