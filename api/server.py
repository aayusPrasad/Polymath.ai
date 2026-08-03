"""
api/server.py
─────────────────────────────────────────────────────────────────────────────
Polymath.ai — Phase 4: FastAPI Server Entrypoint

Wraps the LangGraph multi-agent orchestrator in a REST API. Uses FastAPI
lifespans to load the ChromaDB vector store and compile the LangGraph exactly
once on startup, ensuring sub-second response times for incoming queries.

Endpoints:
    GET  /health  → system status
    POST /query   → invoke the graph and return a structured RAG response

Run:
    uvicorn api.server:app --reload
─────────────────────────────────────────────────────────────────────────────
"""

import sys
import time
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# ── Path setup (allow running from root) ──────────────────────────────────
sys.path.append(str(Path(__file__).parent.parent))

from api.models import QueryRequest, QueryResponse, ErrorResponse
from api.auth import verify_api_key
from agents.orchestrator import _validate_environment, _load_vector_store, build_graph
from ingestion_pipeline import ingest_document

# ── Load environment variables ─────────────────────────────────────────────
load_dotenv()

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("polymath.api")

# Global state container for the lifespan
class AppState:
    vector_store = None
    graph = None


# ── Lifespan Manager ───────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Executes once on server startup.
    Validates API keys, loads the ChromaDB vector store, and compiles the LangGraph.
    """
    log.info("=" * 60)
    log.info("Polymath.ai API Server Starting...")
    log.info("=" * 60)

    try:
        # We reuse the exact same initialisation logic from Phase 3 orchestrator
        api_key = _validate_environment()
        log.info("Pre-flight | GOOGLE_API_KEY detected ✓")

        AppState.vector_store = _load_vector_store(api_key)
        AppState.graph = build_graph(AppState.vector_store, api_key)
        
        log.info("✓ Application state fully loaded and cached in memory.")
    except Exception as exc:
        log.error("Fatal startup error: %s", exc)
        # If the graph can't compile (e.g. ChromaDB is missing), crash early
        raise RuntimeError("Failed to initialise Polymath.ai backend") from exc

    yield  # Server handles requests here

    # Shutdown logic (nothing explicit needed for Chroma/LangGraph)
    log.info("Polymath.ai API Server shutting down...")


# ── FastAPI App Initialisation ─────────────────────────────────────────────
app = FastAPI(
    title="Polymath.ai API",
    description="Multi-agent CS educational tutor API.",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow CORS for potential web frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check():
    """Returns the system status and the number of chunks loaded in ChromaDB."""
    if not AppState.vector_store:
        raise HTTPException(status_code=503, detail="Vector store not loaded")
        
    doc_count = AppState.vector_store._collection.count()
    return {
        "status": "healthy",
        "vector_store_chunks": doc_count,
        "graph_ready": AppState.graph is not None,
    }


@app.post(
    "/query",
    response_model=QueryResponse,
    responses={500: {"model": ErrorResponse}},
    tags=["Query"],
    dependencies=[Depends(verify_api_key)],
)
async def query_polymath(request: QueryRequest):
    """
    Sends a question to the Polymath multi-agent graph.
    Requires X-API-Key header if POLYMATH_API_KEY is set in the environment.
    """
    if not AppState.graph:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Graph is not initialised.",
        )

    question = request.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty.",
        )

    log.info("API | Received query: %r", question)
    t0 = time.perf_counter()

    # The exact same initial state payload we used in Phase 3 CLI
    initial_state = {
        "question":     question,
        "domain":       "",
        "context_docs": [],
        "answer":       "",
        "citations":    [],
        "agent_trace":  [],
    }

    try:
        # invoke() is synchronous, but runs fast enough for a blocking HTTP request
        # in a standard setup. For heavy production traffic, this should be wrapped
        # in a ThreadPoolExecutor or using astream() for SSE.
        result = AppState.graph.invoke(initial_state)
        
        elapsed = time.perf_counter() - t0
        log.info("API | Graph resolved in %.2fs. Routing: %s", elapsed, result.get("domain"))

        return QueryResponse(
            question=result.get("question", ""),
            domain=result.get("domain", "unknown"),
            answer=result.get("answer", ""),
            citations=result.get("citations", []),
            agent_trace=result.get("agent_trace", []),
            processing_time_sec=round(elapsed, 2),
        )

    except Exception as exc:
        log.exception("API | Unexpected error during graph execution: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error processing query: {exc}",
        )

@app.post("/upload", tags=["System"], dependencies=[Depends(verify_api_key)])
async def upload_document(file: UploadFile = File(...)):
    """
    Accepts a PDF upload, chunks/embeds it, and reloads the vector store and graph dynamically.
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    uploads_dir = Path("uploads")
    uploads_dir.mkdir(exist_ok=True)
    
    file_path = uploads_dir / file.filename
    
    try:
        # Save file to disk
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
            
        log.info(f"API | Saved upload to {file_path}. Starting ingestion...")
        
        # Run ingestion
        api_key = _validate_environment()
        chunks_count = ingest_document(str(file_path), api_key)
        
        # Reload vector store and graph so new data is immediately available
        log.info("API | Ingestion complete. Reloading vector store and graph...")
        AppState.vector_store = _load_vector_store(api_key)
        AppState.graph = build_graph(AppState.vector_store, api_key)
        
        return {
            "status": "success", 
            "message": f"Successfully ingested {file.filename}",
            "chunks_added": chunks_count,
            "total_chunks": AppState.vector_store._collection.count()
        }
        
    except Exception as exc:
        log.exception("API | Error processing upload: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

