"""
rag_pipeline.py
─────────────────────────────────────────────────────────────────────────────
Polymath.ai — Phase 2: Retrieval-Augmented Generation (RAG) Pipeline

Loads the persisted ChromaDB vector store produced by Phase 1, wraps it in a
retriever, and chains it with Google's Gemini model to answer questions about
the ingested computer-science documents.

Modes:
    Single query  →  python rag_pipeline.py "What is three-address code?"
    Interactive   →  python rag_pipeline.py   (no argument → REPL loop)

Environment variables (in .env or shell):
    GOOGLE_API_KEY  — your Google Generative AI API key (required)
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import sys
import os
import time
import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# ── Load environment variables from .env (if present) ─────────────────────
load_dotenv()

# ── Logging configuration ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("polymath.rag")

# ── Constants ──────────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR: str = "./chroma_db_polymath"
COLLECTION_NAME: str = "polymath_docs"
EMBEDDING_MODEL: str = "models/gemini-embedding-2-preview"
CHAT_MODEL: str = "gemini-3.5-flash"

# Retriever — fetch top-k most relevant chunks
TOP_K: int = 5

# ── System prompt — tuned for dense CS theory ─────────────────────────────
SYSTEM_PROMPT: str = """\
You are Polymath, a hyper-specialized AI tutor for computer science theory.
You have deep expertise in topics such as compilers, intermediate representations,
three-address code, abstract syntax trees, data-flow analysis, type systems,
algorithm design, and computational complexity.

Rules:
- Answer ONLY from the provided context. If the context does not contain
  enough information, say "I don't have enough information in the loaded
  documents to answer that." Do NOT hallucinate.
- Be precise and technical. Assume the learner has undergraduate CS knowledge.
- When explaining code or pseudocode, format it in fenced code blocks.
- Cite the source page numbers (from document metadata) when available.
- Keep answers concise yet complete. Prefer bullet points for multi-step
  explanations.
"""

RAG_PROMPT_TEMPLATE: str = """\
{system_prompt}

────────────────────── CONTEXT FROM DOCUMENTS ──────────────────────
{context}
─────────────────────────────────────────────────────────────────────

Question: {question}

Answer:"""


# ─────────────────────────────────────────────────────────────────────────────
# Helper utilities
# ─────────────────────────────────────────────────────────────────────────────

def _validate_environment() -> str:
    """Return the Google API key or raise if missing."""
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY is not set. "
            "Export it in your shell or add it to a .env file."
        )
    return api_key


def _validate_chroma_dir() -> Path:
    """Ensure the ChromaDB persist directory exists (produced by Phase 1)."""
    path = Path(CHROMA_PERSIST_DIR).resolve()
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(
            f"ChromaDB directory not found: {path}\n"
            "Run ingestion_pipeline.py first to populate the vector store."
        )
    return path


def _format_docs(docs: list) -> str:
    """Render retrieved documents into a single context block."""
    parts: list[str] = []
    for i, doc in enumerate(docs, start=1):
        meta = doc.metadata
        source = meta.get("source", "unknown")
        page = meta.get("page", "?")
        parts.append(
            f"[Chunk {i} | source: {Path(source).name}, page: {page}]\n"
            f"{doc.page_content.strip()}"
        )
    return "\n\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline initialisation
# ─────────────────────────────────────────────────────────────────────────────

def load_vector_store(api_key: str):
    """Load the persisted ChromaDB vector store (read-only)."""
    from langchain_community.vectorstores import Chroma
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    chroma_path = _validate_chroma_dir()
    log.info("Loading vector store from: %s", chroma_path)

    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=api_key,
    )

    vector_store = Chroma(
        collection_name=COLLECTION_NAME,
        persist_directory=str(chroma_path),
        embedding_function=embeddings,
    )

    doc_count = vector_store._collection.count()
    if doc_count == 0:
        raise ValueError(
            "The ChromaDB collection is empty. "
            "Re-run ingestion_pipeline.py to populate it."
        )

    log.info("✓ Vector store loaded — %d chunk(s) available", doc_count)
    return vector_store


def build_rag_chain(api_key: str, vector_store):
    """
    Assemble the RAG chain using LangChain Expression Language (LCEL).

    Chain structure:
        user_question
            ↓
        retriever          → fetch TOP_K relevant chunks
            ↓
        prompt_template    → inject context + question
            ↓
        ChatGoogleGenerativeAI (Gemini)
            ↓
        StrOutputParser    → clean string answer
    """
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.prompts import PromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.runnables import RunnablePassthrough, RunnableLambda

    log.info("Initialising chat model: %s", CHAT_MODEL)

    llm = ChatGoogleGenerativeAI(
        model=CHAT_MODEL,
        google_api_key=api_key,
        temperature=0.2,          # low temp → precise, reproducible answers
        max_output_tokens=2048,
    )

    retriever = vector_store.as_retriever(
        search_type="mmr",        # Maximal Marginal Relevance — reduces redundancy
        search_kwargs={
            "k": TOP_K,
            "fetch_k": TOP_K * 3, # candidate pool for MMR re-ranking
            "lambda_mult": 0.7,   # 0=max diversity ↔ 1=max relevance
        },
    )

    prompt = PromptTemplate.from_template(RAG_PROMPT_TEMPLATE)

    def retrieve_and_format(question: str) -> dict[str, Any]:
        docs = retriever.invoke(question)
        return {
            "system_prompt": SYSTEM_PROMPT,
            "context": _format_docs(docs),
            "question": question,
            "_source_docs": docs,  # carried through for citation display
        }

    # LCEL chain — each | passes output as input to the next stage
    rag_chain = (
        RunnableLambda(retrieve_and_format)
        | RunnablePassthrough.assign(
            answer=(
                (lambda d: prompt.format(
                    system_prompt=d["system_prompt"],
                    context=d["context"],
                    question=d["question"],
                ))
                | llm
                | StrOutputParser()
            )
        )
    )

    log.info("✓ RAG chain assembled (retriever=MMR, k=%d, model=%s)", TOP_K, CHAT_MODEL)
    return rag_chain, retriever


# ─────────────────────────────────────────────────────────────────────────────
# Query execution
# ─────────────────────────────────────────────────────────────────────────────

def run_query(question: str, rag_chain, retriever) -> None:
    """Execute a single RAG query and print a structured response."""
    log.info("Query received: %r", question)
    t0 = time.perf_counter()

    # Retrieve source docs separately for citation display
    source_docs = retriever.invoke(question)

    # Build prompt manually and call LLM
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langchain_core.messages import HumanMessage

    context_block = _format_docs(source_docs)
    filled_prompt = RAG_PROMPT_TEMPLATE.format(
        system_prompt=SYSTEM_PROMPT,
        context=context_block,
        question=question,
    )

    # Re-use the LLM from the chain
    result = rag_chain.invoke(question)
    answer = result.get("answer", "").strip()

    elapsed = time.perf_counter() - t0

    # ── Pretty print ──────────────────────────────────────────────────────
    divider = "─" * 70
    print(f"\n{divider}")
    print(f"  ❓  {question}")
    print(divider)
    print(f"\n{answer}\n")

    # ── Source citations ──────────────────────────────────────────────────
    if source_docs:
        print(divider)
        print("  📚  Sources retrieved:")
        seen: set[str] = set()
        for doc in source_docs:
            meta = doc.metadata
            src = Path(meta.get("source", "unknown")).name
            page = meta.get("page", "?")
            label = f"    • {src}  (page {page})"
            if label not in seen:
                print(label)
                seen.add(label)

    print(f"\n  ⏱  Answered in {elapsed:.2f}s")
    print(divider + "\n")


# ─────────────────────────────────────────────────────────────────────────────
# Interactive REPL
# ─────────────────────────────────────────────────────────────────────────────

REPL_BANNER = """
╔══════════════════════════════════════════════════════════════════════╗
║          Polymath.ai — Interactive CS Tutor  (Phase 2)             ║
║  Type your question and press Enter.  Type 'exit' or 'quit' to stop. ║
╚══════════════════════════════════════════════════════════════════════╝
"""

def run_repl(rag_chain, retriever) -> None:
    """Start an interactive query loop."""
    print(REPL_BANNER)
    while True:
        try:
            question = input("Polymath › ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not question:
            continue
        if question.lower() in {"exit", "quit", "q"}:
            print("Goodbye!")
            break

        try:
            run_query(question, rag_chain, retriever)
        except Exception as exc:  # noqa: BLE001
            log.error("Query failed: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 70)
    log.info("Polymath.ai — RAG Pipeline  |  Phase 2")
    log.info("=" * 70)

    # ── Pre-flight ─────────────────────────────────────────────────────────
    try:
        api_key = _validate_environment()
        log.info("Pre-flight | GOOGLE_API_KEY detected ✓")

        vector_store = load_vector_store(api_key)
        rag_chain, retriever = build_rag_chain(api_key, vector_store)

    except EnvironmentError as exc:
        log.error("Configuration error: %s", exc)
        sys.exit(2)
    except FileNotFoundError as exc:
        log.error("File error: %s", exc)
        sys.exit(3)
    except ValueError as exc:
        log.error("Validation error: %s", exc)
        sys.exit(4)
    except Exception as exc:  # noqa: BLE001
        log.exception("Startup error: %s", exc)
        sys.exit(99)

    # ── Dispatch ───────────────────────────────────────────────────────────
    if len(sys.argv) > 1:
        # Single-query mode: question passed as a CLI argument
        question = " ".join(sys.argv[1:]).strip()
        try:
            run_query(question, rag_chain, retriever)
        except Exception as exc:  # noqa: BLE001
            log.exception("Query error: %s", exc)
            sys.exit(5)
    else:
        # Interactive REPL mode
        run_repl(rag_chain, retriever)


if __name__ == "__main__":
    main()
