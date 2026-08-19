"""
ingestion_pipeline.py
─────────────────────────────────────────────────────────────────────────────
Polymath.ai — Phase 1: Document Ingestion Pipeline

Loads a local PDF, splits it into semantically coherent chunks tuned for
dense computer-science theory (IRs, three-address code, syntax trees), embeds
each chunk with Google's gemini-embedding-2-preview model, and persists the resulting
vector store to a local ChromaDB directory.

Usage:
    python ingestion_pipeline.py <path/to/document.pdf>

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

from dotenv import load_dotenv

# ── Load environment variables from .env (if present) ─────────────────────
load_dotenv()

# ── Logging configuration ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("polymath.ingestion")

# ── Constants ──────────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR: str = "./chroma_db_polymath"
COLLECTION_NAME: str = "polymath_docs"
EMBEDDING_MODEL: str = "models/gemini-embedding-2-preview"

# Splitter config — tuned for dense CS theory prose + code blocks
CHUNK_SIZE: int = 1_000
CHUNK_OVERLAP: int = 150

# If PyMuPDF extracts fewer than this many chars per page on average,
# the PDF is treated as image-based and OCR is triggered automatically.
OCR_CHARS_PER_PAGE_THRESHOLD: int = 50

# Separators: double-newline (paragraphs) first, then code-fence boundaries,
# then single newline, then sentence/sub-sentence boundaries.
SEPARATORS: list[str] = [
    "\n\n",          # paragraph breaks
    "```",           # code-fence delimiter (Markdown / RST)
    "\n",            # line breaks
    ". ",            # sentence boundary
    ", ",            # clause boundary
    " ",             # word boundary
    "",              # character fallback
]


# ─────────────────────────────────────────────────────────────────────────────
# Helper utilities
# ─────────────────────────────────────────────────────────────────────────────

def _validate_environment() -> str:
    """Return the Google API key or raise if it is missing."""
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY is not set. "
            "Export it in your shell or add it to a .env file."
        )
    return api_key


def _validate_pdf_path(raw_path: str) -> Path:
    """Return a resolved Path to the PDF, raising on any file-system error."""
    path = Path(raw_path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    if not path.is_file():
        raise ValueError(f"Path is not a regular file: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(
            f"Expected a .pdf file but received: {path.suffix!r} ({path})"
        )
    return path


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline stages
# ─────────────────────────────────────────────────────────────────────────────

def _ocr_pdf_with_gemini(pdf_path: Path, api_key: str) -> list:
    """OCR fallback — render each page as an image and extract text via Gemini Vision."""
    import fitz  # PyMuPDF
    import base64
    import google.generativeai as genai
    from langchain.schema import Document

    genai.configure(api_key=api_key)
    vision_model = genai.GenerativeModel("gemini-3.5-flash")

    log.info("Stage 1 | OCR | Opening PDF with PyMuPDF for image rendering...")
    doc = fitz.open(str(pdf_path))
    documents = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        # Render at 2x resolution for better OCR accuracy
        mat = fitz.Matrix(2, 2)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        b64_img = base64.b64encode(img_bytes).decode("utf-8")

        log.info("Stage 1 | OCR | Processing page %d/%d...", page_num + 1, len(doc))

        try:
            response = vision_model.generate_content([
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": b64_img
                            }
                        },
                        {
                            "text": (
                                "You are an OCR engine. Extract ALL text from this page exactly as written. "
                                "Preserve structure, headings, bullet points, formulas, and code. "
                                "Return only the extracted text, no explanations."
                            )
                        }
                    ]
                }
            ])
            text = response.text.strip()
        except Exception as exc:
            log.warning("Stage 1 | OCR | Page %d failed: %s", page_num + 1, exc)
            text = ""

        if text:
            documents.append(Document(
                page_content=text,
                metadata={
                    "source": str(pdf_path),
                    "page": page_num,
                    "file_path": str(pdf_path),
                    "ocr": True,
                }
            ))

    doc.close()
    log.info("Stage 1 | OCR | ✓ Extracted text from %d/%d page(s)", len(documents), len(doc))
    return documents


def load_pdf(pdf_path: Path, api_key: str = ""):
    """Stage 1 — Load PDF pages via PyMuPDFLoader, with automatic OCR fallback."""
    from langchain_community.document_loaders import PyMuPDFLoader

    log.info("Stage 1 | Loading PDF: %s", pdf_path)
    t0 = time.perf_counter()

    loader = PyMuPDFLoader(str(pdf_path))
    documents = loader.load()

    elapsed = time.perf_counter() - t0
    log.info(
        "Stage 1 | ✓ Loaded %d page(s) in %.2fs", len(documents), elapsed
    )

    # Detect image-based/scanned PDFs by checking average chars per page
    if documents:
        total_chars = sum(len(d.page_content) for d in documents)
        avg_chars = total_chars / len(documents)
        log.info("Stage 1 | Avg chars/page: %.0f", avg_chars)

        if avg_chars < OCR_CHARS_PER_PAGE_THRESHOLD:
            log.warning(
                "Stage 1 | Sparse text detected (%.0f chars/page avg). "
                "PDF appears to be scanned/handwritten. Triggering Gemini Vision OCR...",
                avg_chars
            )
            if not api_key:
                raise ValueError(
                    "OCR is required for this PDF but no API key was provided."
                )
            documents = _ocr_pdf_with_gemini(pdf_path, api_key)

    return documents


def split_documents(documents):
    """Stage 2 — Chunk documents with RecursiveCharacterTextSplitter."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    log.info(
        "Stage 2 | Splitting %d page(s) → chunk_size=%d, overlap=%d",
        len(documents),
        CHUNK_SIZE,
        CHUNK_OVERLAP,
    )
    t0 = time.perf_counter()

    splitter = RecursiveCharacterTextSplitter(
        separators=SEPARATORS,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        is_separator_regex=False,   # treat separators as plain strings
    )
    chunks = splitter.split_documents(documents)

    elapsed = time.perf_counter() - t0
    log.info(
        "Stage 2 | ✓ Created %d chunk(s) from %d page(s) in %.2fs",
        len(chunks),
        len(documents),
        elapsed,
    )

    if not chunks:
        raise ValueError(
            "Text splitter produced 0 chunks. "
            "The PDF may be image-only (no extractable text)."
        )

    # Quick diagnostics: token distribution
    sizes = [len(c.page_content) for c in chunks]
    log.info(
        "Stage 2 | Chunk size stats — min: %d  max: %d  avg: %.0f chars",
        min(sizes),
        max(sizes),
        sum(sizes) / len(sizes),
    )

    return chunks


def build_embeddings(api_key: str):
    """Stage 3 — Initialise Google Generative AI Embeddings."""
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    log.info(
        "Stage 3 | Initialising embedding model: %s", EMBEDDING_MODEL
    )
    embeddings = GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=api_key,
    )
    log.info("Stage 3 | ✓ Embedding model ready")
    return embeddings


def persist_to_chroma(chunks, embeddings):
    """Stage 4 — Embed chunks and persist vector store to ChromaDB."""
    from langchain_community.vectorstores import Chroma

    persist_path = Path(CHROMA_PERSIST_DIR).resolve()
    log.info(
        "Stage 4 | Persisting %d chunk(s) → ChromaDB at: %s",
        len(chunks),
        persist_path,
    )
    t0 = time.perf_counter()

    # Chroma.from_documents embeds + stores in a single call.
    # persist_directory tells Chroma to write the SQLite + index files there.
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=str(persist_path),
    )

    # Chroma >= 0.4 auto-persists; calling persist() is a no-op but harmless.
    # Kept here as an explicit, self-documenting safety net.
    if hasattr(vector_store, "persist"):
        vector_store.persist()

    elapsed = time.perf_counter() - t0
    collection_count = vector_store._collection.count()  # direct count check

    log.info(
        "Stage 4 | ✓ Vector store saved in %.2fs — "
        "collection '%s' now holds %d document(s)",
        elapsed,
        COLLECTION_NAME,
        collection_count,
    )

    return vector_store


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def ingest_document(pdf_path_str: str, api_key: str) -> int:
    """Core logic to ingest a single document without side effects like sys.exit."""
    pdf_path = _validate_pdf_path(pdf_path_str)
    log.info("Pre-flight | PDF path validated: %s", pdf_path)

    documents = load_pdf(pdf_path, api_key=api_key)
    chunks = split_documents(documents)
    embeddings = build_embeddings(api_key)
    persist_to_chroma(chunks, embeddings)
    
    return len(chunks)


def run_pipeline(pdf_path_str: str) -> None:
    """Execute the full ingestion pipeline end-to-end (CLI entrypoint)."""
    log.info("=" * 70)
    log.info("Polymath.ai — Ingestion Pipeline  |  Phase 1")
    log.info("=" * 70)

    # ── Pre-flight checks ──────────────────────────────────────────────────
    api_key = _validate_environment()
    log.info("Pre-flight | GOOGLE_API_KEY detected ✓")

    chunks_count = ingest_document(pdf_path_str, api_key)  # OCR fallback included

    log.info("=" * 70)
    log.info(
        "Pipeline complete. %d chunks embedded and persisted to '%s'.",
        chunks_count,
        CHROMA_PERSIST_DIR,
    )
    log.info("=" * 70)


def main() -> None:
    if len(sys.argv) != 2:
        print(
            "Usage: python ingestion_pipeline.py <path/to/document.pdf>",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        run_pipeline(sys.argv[1])
    except EnvironmentError as exc:
        log.error("Configuration error: %s", exc)
        sys.exit(2)
    except FileNotFoundError as exc:
        log.error("File error: %s", exc)
        sys.exit(3)
    except ValueError as exc:
        log.error("Validation error: %s", exc)
        sys.exit(4)
    except KeyboardInterrupt:
        log.warning("Interrupted by user.")
        sys.exit(130)
    except Exception as exc:  # noqa: BLE001
        log.exception("Unexpected error during ingestion: %s", exc)
        sys.exit(99)


if __name__ == "__main__":
    main()
