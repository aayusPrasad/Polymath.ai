"""
agents/orchestrator.py
─────────────────────────────────────────────────────────────────────────────
Polymath.ai — Phase 3: Master LangGraph Orchestration + CLI

Wires the Router Node and four Domain Specialist Agents into a compiled
LangGraph StateGraph, then exposes two execution modes:

    Single query  →  python agents/orchestrator.py "What is three-address code?"
    Interactive   →  python agents/orchestrator.py   (REPL loop)

Graph topology
──────────────
    START
      │
      ▼
   [router]  ←──── classifies domain via structured LLM output
      │
      │  conditional edge  (lambda s: s["domain"])
      │
      ├──► [compiler_theory]  ──► END
      ├──► [algorithms]       ──► END
      ├──► [theory_of_comp]   ──► END
      └──► [general_cs]       ──► END

Prerequisites
─────────────
    • ./chroma_db_polymath  must exist  (run ingestion_pipeline.py first)
    • GOOGLE_API_KEY        must be set (shell export or .env file)
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# ── Path setup ─────────────────────────────────────────────────────────────
# Allow running `python agents/orchestrator.py` by adding the project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

# Force UTF-8 output to prevent Windows cp1252 charmap crashes when printing emojis/borders
sys.stdout.reconfigure(encoding='utf-8')

# ── Load .env before anything else ────────────────────────────────────────
load_dotenv()

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("polymath.orchestrator")

# ── Constants ──────────────────────────────────────────────────────────────
CHROMA_PERSIST_DIR: str = "./chroma_db_polymath"
COLLECTION_NAME:    str = "polymath_docs"
EMBEDDING_MODEL:    str = "models/gemini-embedding-2-preview"
CHAT_MODEL:         str = "gemini-3.5-flash"   # swap to gemini-3.5-pro for deeper reasoning

# Maps domain keys → human-readable labels for CLI output
DOMAIN_DISPLAY: dict[str, str] = {
    "compiler_theory": "⚙️   Compiler Theory",
    "algorithms":      "📊  Algorithms & Data Structures",
    "theory_of_comp":  "🧮  Theory of Computation",
    "general_cs":      "🖥️   General Computer Science",
}


# ─────────────────────────────────────────────────────────────────────────────
# Pre-flight helpers
# ─────────────────────────────────────────────────────────────────────────────

def _validate_environment() -> str:
    """Return GOOGLE_API_KEY or raise EnvironmentError."""
    api_key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError(
            "GOOGLE_API_KEY is not set. "
            "Export it in your shell or add it to a .env file."
        )
    return api_key


def _load_vector_store(api_key: str):
    """
    Load the persisted ChromaDB vector store produced by Phase 1.

    Raises FileNotFoundError if the persist directory does not exist, and
    ValueError if the collection is empty (Phase 1 was not run successfully).
    """
    from langchain_community.vectorstores import Chroma
    from langchain_google_genai import GoogleGenerativeAIEmbeddings

    chroma_path = Path(CHROMA_PERSIST_DIR).resolve()
    if not chroma_path.exists():
        log.info("Creating empty ChromaDB directory at: %s", chroma_path)
        chroma_path.mkdir(parents=True, exist_ok=True)

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
        log.warning("ChromaDB collection is empty. Please upload documents to populate the vector store.")
    else:
        log.info("✓ Vector store ready — %d chunks available", doc_count)
    return vector_store



# ─────────────────────────────────────────────────────────────────────────────
# Graph builder
# ─────────────────────────────────────────────────────────────────────────────

def build_graph(vector_store, api_key: str):
    """
    Assemble and compile the LangGraph StateGraph for Polymath.ai Phase 3.

    Steps
    ─────
    1. Initialise a single shared ChatGoogleGenerativeAI LLM instance.
    2. Instantiate all four SpecialistAgent objects (bound to the shared LLM
       and vector store).
    3. Build a StateGraph(PolymathState), adding nodes and edges.
    4. Compile and return the runnable graph.

    Parameters
    ----------
    vector_store:
        Pre-loaded Chroma instance from _load_vector_store().
    api_key:
        Google Generative AI API key.

    Returns
    -------
    CompiledGraph
        A LangGraph compiled graph ready to be invoked with an initial state dict.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI
    from langgraph.graph import END, START, StateGraph

    from agents.router import router_node
    from agents.specialists import SPECIALIST_CONFIGS, SpecialistAgent
    from agents.state import PolymathState

    log.info("Initialising LLM: %s", CHAT_MODEL)
    llm = ChatGoogleGenerativeAI(
        model=CHAT_MODEL,
        google_api_key=api_key,
        temperature=0.1,        # low temperature → precise, reproducible answers
        max_output_tokens=2048,
    )
    log.info("✓ LLM ready")

    # ── Instantiate specialist agents ──────────────────────────────────────
    log.info("Instantiating %d specialist agent(s)…", len(SPECIALIST_CONFIGS))
    specialists: dict[str, SpecialistAgent] = {
        domain_key: SpecialistAgent(
            domain_key=domain_key,
            config=config,
            vector_store=vector_store,
            llm=llm,
        )
        for domain_key, config in SPECIALIST_CONFIGS.items()
    }
    log.info("✓ Specialist agents ready: %s", list(specialists.keys()))

    # ── Build StateGraph ───────────────────────────────────────────────────
    log.info("Building StateGraph…")
    graph_builder: StateGraph = StateGraph(PolymathState)

    # Router node: wrap router_node to bind the shared LLM via closure.
    # LangGraph node callables must accept only (state) → dict.
    def _router_node(state: PolymathState) -> dict:
        return router_node(state, llm)

    graph_builder.add_node("router", _router_node)

    # Specialist nodes — each SpecialistAgent.__call__ already matches the
    # LangGraph node signature: (state: PolymathState) -> dict
    for domain_key, agent in specialists.items():
        graph_builder.add_node(domain_key, agent)

    # ── Edges ──────────────────────────────────────────────────────────────

    # START → router (always)
    graph_builder.add_edge(START, "router")

    # router → one specialist  (conditional, driven by state["domain"])
    graph_builder.add_conditional_edges(
        source="router",
        path=lambda state: state["domain"],
        path_map={
            "compiler_theory": "compiler_theory",
            "algorithms":      "algorithms",
            "theory_of_comp":  "theory_of_comp",
            "general_cs":      "general_cs",
        },
    )

    # Each specialist → END
    for domain_key in SPECIALIST_CONFIGS:
        graph_builder.add_edge(domain_key, END)

    # ── Compile ────────────────────────────────────────────────────────────
    compiled_graph = graph_builder.compile()
    log.info("✓ LangGraph StateGraph compiled and ready")
    return compiled_graph


# ─────────────────────────────────────────────────────────────────────────────
# Query execution + display
# ─────────────────────────────────────────────────────────────────────────────

def _build_initial_state(question: str) -> dict:
    """
    Construct a clean initial PolymathState dict for a new graph invocation.

    All fields must be present even if empty — LangGraph requires the TypedDict
    to be fully initialised at graph entry.
    """
    return {
        "question":     question,
        "domain":       "",       # filled by router_node
        "context_docs": [],       # filled by specialist
        "answer":       "",       # filled by specialist
        "citations":    [],       # filled by specialist
        "agent_trace":  [],       # appended to by every node
    }


# ── Pretty-print helpers ───────────────────────────────────────────────────

_WIDE  = "═" * 72
_THIN  = "─" * 72


def _print_result(result: dict, elapsed: float) -> None:
    """
    Render a completed graph result to stdout in a structured, readable format.

    Sections printed
    ────────────────
    1. Question
    2. Routing decision (domain + display label)
    3. Answer (verbatim — may contain Markdown)
    4. Source citations (deduplicated page refs)
    5. Agent audit trace (step-by-step path through the graph)
    6. Total wall-clock time
    """
    question  = result.get("question",     "").strip()
    domain    = result.get("domain",       "unknown")
    answer    = result.get("answer",       "").strip()
    citations = result.get("citations",    [])
    trace     = result.get("agent_trace",  [])

    domain_label = DOMAIN_DISPLAY.get(domain, f"🔍  {domain}")

    # ── Header ─────────────────────────────────────────────────────────────
    print(f"\n{_WIDE}")
    print(f"  ❓  {question}")
    print(_WIDE)

    # ── Routing decision ───────────────────────────────────────────────────
    print(f"\n  🔀  Routed to  →  {domain_label}")
    print(_THIN)

    # ── Answer ─────────────────────────────────────────────────────────────
    print(f"\n{answer}\n")

    # ── Citations ──────────────────────────────────────────────────────────
    if citations:
        print(_THIN)
        print("  📚  Sources:")
        for cite in citations:
            print(f"       • {cite}")

    # ── Agent Audit Trace ──────────────────────────────────────────────────
    if trace:
        print(_THIN)
        print("  🔍  Agent Audit Trace:")
        for i, entry in enumerate(trace, start=1):
            print(f"       {i}.  {entry}")

    # ── Timing footer ──────────────────────────────────────────────────────
    print(_THIN)
    print(f"  ⏱   Total wall time: {elapsed:.2f}s")
    print(f"{_WIDE}\n")


def run_query(graph, question: str) -> None:
    """
    Invoke the compiled graph for a single question and display the result.

    Raises
    ------
    Propagates any graph invocation exception to the caller for handling.
    """
    question = question.strip()
    if not question:
        log.warning("Empty question received — skipping.")
        return

    log.info("Invoking graph  |  question: %r", question)
    initial_state = _build_initial_state(question)

    t0     = time.perf_counter()
    result = graph.invoke(initial_state)
    elapsed = time.perf_counter() - t0

    log.info("Graph completed in %.2fs", elapsed)
    _print_result(result, elapsed)


# ─────────────────────────────────────────────────────────────────────────────
# Interactive REPL
# ─────────────────────────────────────────────────────────────────────────────

_REPL_BANNER = """
╔══════════════════════════════════════════════════════════════════════════╗
║      Polymath.ai  ·  Multi-Agent CS Tutor  ·  Phase 3 (LangGraph)      ║
║                                                                          ║
║  Domains  →  ⚙️  Compiler Theory   📊 Algorithms   🧮 Theory of Comp   ║
║               🖥️  General CS  (auto-routed — just ask!)                  ║
║                                                                          ║
║  Commands →  exit | quit | q   to stop the session                      ║
╚══════════════════════════════════════════════════════════════════════════╝
"""

def run_repl(graph) -> None:
    """Start an interactive REPL session backed by the compiled graph."""
    print(_REPL_BANNER)

    while True:
        try:
            raw = input("Polymath › ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nSession ended.  Goodbye!")
            break

        if not raw:
            continue

        if raw.lower() in {"exit", "quit", "q"}:
            print("Goodbye!")
            break

        try:
            run_query(graph, raw)
        except Exception as exc:  # noqa: BLE001
            log.error("Query failed (%s: %s) — please try again.", type(exc).__name__, exc)


# ─────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    log.info("=" * 72)
    log.info("Polymath.ai — Multi-Agent Orchestrator  |  Phase 3")
    log.info("=" * 72)

    # ── Pre-flight ─────────────────────────────────────────────────────────
    try:
        api_key      = _validate_environment()
        log.info("Pre-flight | GOOGLE_API_KEY detected ✓")

        vector_store = _load_vector_store(api_key)
        graph        = build_graph(vector_store, api_key)

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
        # Single-query mode: question is every CLI token after the script name
        question = " ".join(sys.argv[1:]).strip()
        try:
            run_query(graph, question)
        except Exception as exc:  # noqa: BLE001
            log.exception("Query error: %s", exc)
            sys.exit(5)
    else:
        # Interactive REPL mode
        run_repl(graph)


if __name__ == "__main__":
    main()
