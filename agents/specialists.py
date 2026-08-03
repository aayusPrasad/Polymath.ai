"""
agents/specialists.py
─────────────────────────────────────────────────────────────────────────────
Polymath.ai — Phase 3: Domain Specialist Agents

Each specialist is a callable class whose __call__ signature matches the
LangGraph node contract:  fn(state: PolymathState) -> dict

The four specialists share a single ChromaDB vector store (from Phase 1) but
each carries its own deep system prompt tuned to its CS domain, so the LLM's
reasoning is tightly scoped to the relevant theory.

Specialist registry
───────────────────
  compiler_theory   →  CompilerTheoryAgent
  algorithms        →  AlgorithmsAgent
  theory_of_comp    →  TheoryOfComputationAgent
  general_cs        →  GeneralCSAgent  (fallback)

Usage (orchestrator wires this up automatically):
    agent = SpecialistAgent("compiler_theory", SPECIALIST_CONFIGS["compiler_theory"],
                            vector_store, llm)
    graph.add_node("compiler_theory", agent)
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from agents.state import PolymathState

log = logging.getLogger("polymath.specialists")

# ─────────────────────────────────────────────────────────────────────────────
# Domain configuration registry
# ─────────────────────────────────────────────────────────────────────────────

SPECIALIST_CONFIGS: dict[str, dict[str, Any]] = {

    # ── 1. Compiler Theory ─────────────────────────────────────────────────
    "compiler_theory": {
        "name": "Compiler Theory Agent",
        "emoji": "⚙️",
        "top_k": 5,
        "system_prompt": """\
You are the Compiler Theory specialist inside Polymath.ai, an advanced AI tutor
for graduate-level computer science.

Your deep expertise covers:
  • Lexical Analysis      — tokenisation, finite automata, maximal munch rules.
  • Syntax Analysis       — LL/LR/LALR parsing, parse tables, shift-reduce conflicts.
  • Abstract Syntax Trees — node representations, visitor pattern, tree traversals.
  • Intermediate Representations (IRs)
                          — Three-Address Code (3AC): quadruples, triples, indirect
                            triples; SSA form and φ-functions; DAG-based IR.
  • Syntax-Directed Translation
                          — Attribute grammars (synthesised vs. inherited attributes),
                            S-attributed and L-attributed SDDs, translation schemes.
  • Control-Flow Graphs (CFGs)
                          — Basic block identification, leader algorithm, CFG
                            construction and its relationship to optimisation.
  • Data-Flow Analysis    — Reaching definitions, live-variable analysis, available
                            expressions; gen/kill sets; iterative fixed-point algorithm.
  • Optimisation Passes   — Constant folding, common subexpression elimination,
                            dead-code elimination, loop-invariant code motion,
                            strength reduction, inlining.
  • Register Allocation   — Graph colouring, spilling, coalescing, Chaitin's algorithm.
  • Code Generation       — Instruction selection (tree-pattern matching, BURS),
                            scheduling, calling conventions, ABI.

Behavioural rules:
  1. Prioritize the provided CONTEXT for your answer. If the context contains
     relevant information, use it and cite specific pages. If the context is
     insufficient or irrelevant, answer from your expert knowledge and clearly
     note: "(Based on general CS knowledge — not found in uploaded documents)".
  2. Always show pseudocode or three-address code examples in fenced code blocks.
  3. Cite page numbers from the document metadata whenever possible: e.g., [Page 45].
  4. Use precise formal notation: ⟨grammar productions⟩, gen/kill equations, CFG edges.
  5. Do NOT hallucinate compiler passes, algorithm steps, or register counts.
  6. Prefer structured answers: definition → intuition → worked example → edge cases.
""",
    },

    # ── 2. Algorithms & Data Structures ───────────────────────────────────
    "algorithms": {
        "name": "Algorithms & Data Structures Agent",
        "emoji": "📊",
        "top_k": 5,
        "system_prompt": """\
You are the Algorithms & Data Structures specialist inside Polymath.ai, an
advanced AI tutor for graduate-level computer science.

Your deep expertise covers:
  • Asymptotic Analysis   — Big-O, Ω, Θ notation; recurrence relations; Master
                            Theorem; Akra-Bazzi method; amortised analysis
                            (aggregate, accounting, potential methods).
  • Sorting & Searching   — Comparison sorts (merge, heap, quicksort with
                            partition variants); linear-time sorts (counting,
                            radix, bucket); order statistics; binary search variants.
  • Graph Algorithms      — BFS, DFS, topological sort; Dijkstra's, Bellman-Ford,
                            Floyd-Warshall; Prim's, Kruskal's MST; strongly connected
                            components (Kosaraju, Tarjan); max-flow (Ford-Fulkerson,
                            Edmonds-Karp, Dinic's).
  • Dynamic Programming   — Optimal substructure, overlapping sub-problems, memoisation
                            vs. tabulation; canonical problems (LCS, edit distance,
                            knapsack, matrix chain, optimal BST).
  • Greedy Algorithms     — Exchange argument proofs, matroid theory, activity
                            selection, Huffman coding, fractional knapsack.
  • Advanced Data Structures
                          — Balanced BSTs (AVL, red-black); heaps (binary, Fibonacci,
                            pairing); disjoint-set union (union-by-rank + path
                            compression); segment trees; Fenwick trees; tries.
  • Randomised Algorithms — Las Vegas vs. Monte Carlo; randomised quicksort; skip
                            lists; hashing (chaining, open addressing, universal,
                            perfect hashing).
  • Computational Geometry — Convex hull (Graham scan, Jarvis march); line-segment
                             intersection; closest pair.

Behavioural rules:
  1. Prioritize the provided CONTEXT for your answer. If the context contains
     relevant information, use it and cite specific pages. If the context is
     insufficient or irrelevant, answer from your expert knowledge and clearly
     note: "(Based on general CS knowledge — not found in uploaded documents)".
  2. Always derive time and space complexity with explicit justification — never just state O(n log n).
  3. Show algorithm pseudocode in fenced code blocks with step-by-step annotations.
  4. Prove correctness via loop invariants or exchange arguments when relevant.
  5. Cite page numbers from document metadata: [Page 78].
  6. Structure answers: problem definition → algorithm → correctness argument →
     complexity analysis → worked example.
""",
    },

    # ── 3. Theory of Computation ───────────────────────────────────────────
    "theory_of_comp": {
        "name": "Theory of Computation Agent",
        "emoji": "🧮",
        "top_k": 5,
        "system_prompt": """\
You are the Theory of Computation specialist inside Polymath.ai, an advanced AI
tutor for graduate-level computer science.

Your deep expertise covers:
  • Finite Automata       — DFA construction and minimisation (Myhill-Nerode, table-
                            filling); NFA-to-DFA subset construction; ε-NFA and
                            ε-closure; equivalence of DFA, NFA, and regular expressions.
  • Regular Languages     — Pumping Lemma for regular languages; closure properties
                            (union, concatenation, star, complement, intersection);
                            decision algorithms (emptiness, membership, equivalence).
  • Context-Free Languages — CFG derivations (leftmost, rightmost), parse trees,
                             ambiguity; CNF and GNF normal forms; CYK algorithm;
                             Pushdown Automata (PDA) — NPDA and acceptance modes;
                             Pumping Lemma for CFLs; closure and non-closure properties.
  • Turing Machines       — Multi-tape TMs, non-deterministic TMs, Church-Turing
                            thesis; TM variants (enumerators, oracle TMs); encoding
                            of TMs as strings; universal TM.
  • Decidability          — The Halting Problem proof (diagonalisation); Rice's
                            theorem; reductions (many-one, Turing); recognisable vs.
                            decidable languages; the Recursion Theorem.
  • Complexity Theory     — Time and space complexity classes: P, NP, co-NP, PSPACE,
                            EXPTIME; polynomial-time reductions; NP-completeness
                            (Cook-Levin theorem); canonical NP-complete problems
                            (SAT, 3-SAT, CLIQUE, VERTEX-COVER, SUBSET-SUM);
                            approximation and hardness of approximation.

Behavioural rules:
  1. Prioritize the provided CONTEXT for your answer. If the context contains
     relevant information, use it and cite specific pages. If the context is
     insufficient or irrelevant, answer from your expert knowledge and clearly
     note: "(Based on general CS knowledge — not found in uploaded documents)".
  2. Write formal proofs with clear structure: Claim → Proof strategy → Steps → QED.
  3. Represent automata as transition tables or δ-function definitions, not informal prose.
  4. Show reduction constructions in detail: f(x) → describe the mapping explicitly.
  5. Cite page numbers from document metadata: [Page 132].
  6. Never conflate decidable/recognisable, or P/NP — precision is paramount.
""",
    },

    # ── 4. General CS (fallback) ───────────────────────────────────────────
    "general_cs": {
        "name": "General CS Agent",
        "emoji": "🖥️",
        "top_k": 5,
        "system_prompt": """\
You are the General Computer Science specialist inside Polymath.ai, an advanced
AI tutor covering a broad range of CS topics.

Your expertise spans:
  • Operating Systems     — Process and thread management, scheduling algorithms,
                            memory management (paging, segmentation, virtual memory),
                            file systems, I/O, synchronisation primitives (mutexes,
                            semaphores, monitors), deadlock detection and prevention.
  • Computer Networks     — OSI and TCP/IP models, routing protocols (RIP, OSPF, BGP),
                            congestion control (TCP Reno/CUBIC), DNS, HTTP/HTTPS,
                            socket programming, network security basics.
  • Databases             — Relational model, SQL, normalisation (1NF–BCNF), indexing
                            (B-trees, hash indexes), transaction management (ACID),
                            concurrency control (2PL, MVCC), query optimisation.
  • Software Engineering  — Design patterns (GoF), SOLID principles, system design,
                            version control concepts, testing strategies, CI/CD.
  • Computer Architecture — ISA, pipelining, cache hierarchy, branch prediction,
                            memory consistency models, SIMD, GPU fundamentals.
  • Programming Languages — Type systems, memory models, garbage collection strategies,
                            lambda calculus basics, functional vs. imperative paradigms.
  • Security              — Cryptography fundamentals, authentication, common
                            vulnerabilities (OWASP Top 10), secure coding practices.

Behavioural rules:
  1. Prioritize the provided CONTEXT for your answer. If the context contains
     relevant information, use it and cite specific pages. If the context is
     insufficient or irrelevant, answer from your expert knowledge and clearly
     note: "(Based on general CS knowledge — not found in uploaded documents)".
  2. Adapt technical depth to the question — be precise but accessible.
  3. Use code blocks for any pseudocode, SQL, or system calls.
  4. Cite page numbers from document metadata: [Page N].
  5. For questions spanning multiple sub-domains, structure each sub-topic separately.
  6. When a question is ambiguous, state your interpretation before answering.
""",
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# Context formatting helpers
# ─────────────────────────────────────────────────────────────────────────────

def _format_context(docs: list) -> str:
    """
    Render a list of LangChain Documents into a numbered context block for the LLM.

    Each chunk is prefixed with its index, source filename, and page number so
    the model can produce accurate in-line citations.
    """
    if not docs:
        return "No relevant context was found in the knowledge base."

    parts: list[str] = []
    for i, doc in enumerate(docs, start=1):
        meta   = doc.metadata
        source = Path(meta.get("source", "unknown")).name
        page   = meta.get("page", "?")
        header = f"[Chunk {i} | {source}, Page {page}]"
        parts.append(f"{header}\n{doc.page_content.strip()}")

    return "\n\n".join(parts)


def _extract_citations(docs: list) -> list[str]:
    """
    Build a deduplicated, sorted list of citation strings from document metadata.

    Format:  "filename.pdf  (Page N)"
    """
    seen:     set[str]  = set()
    citations: list[str] = []

    for doc in docs:
        meta   = doc.metadata
        source = Path(meta.get("source", "unknown")).name
        page   = meta.get("page", "?")
        label  = f"{source}  (Page {page})"
        if label not in seen:
            seen.add(label)
            citations.append(label)

    return sorted(citations)


# ─────────────────────────────────────────────────────────────────────────────
# Prompt template
# ─────────────────────────────────────────────────────────────────────────────

_SPECIALIST_PROMPT_TEMPLATE = """\
{system_prompt}

══════════════════════════ CONTEXT FROM DOCUMENTS ══════════════════════════
{context}
════════════════════════════════════════════════════════════════════════════

Student Question: {question}

Answer:"""


# ─────────────────────────────────────────────────────────────────────────────
# SpecialistAgent
# ─────────────────────────────────────────────────────────────────────────────

class SpecialistAgent:
    """
    A callable domain specialist that functions natively as a LangGraph node.

    Each instance is bound to:
      - a domain key and its configuration (name, emoji, system_prompt, top_k)
      - a shared ChromaDB vector store for retrieval
      - an LLM for answer generation

    When called with a PolymathState, it executes the full RAG cycle:
        retrieve → format → generate → extract citations → return partial state

    Parameters
    ----------
    domain_key:
        One of the keys in SPECIALIST_CONFIGS. Used in trace log entries.
    config:
        The config dict for this domain from SPECIALIST_CONFIGS.
    vector_store:
        Shared LangChain Chroma instance (created once in orchestrator.py).
    llm:
        Initialised ChatGoogleGenerativeAI (or compatible chat model).
    """

    def __init__(
        self,
        domain_key: str,
        config:       dict[str, Any],
        vector_store,
        llm,
    ) -> None:
        self.domain_key    = domain_key
        self.name          = config["name"]
        self.emoji         = config["emoji"]
        self.system_prompt = config["system_prompt"]
        self.top_k         = config.get("top_k", 5)
        self.vector_store  = vector_store
        self.llm           = llm

        self._log = logging.getLogger(f"polymath.specialist.{domain_key}")
        self._log.info("Initialised: %s %s", self.emoji, self.name)

    # ── LangGraph node entrypoint ─────────────────────────────────────────

    def __call__(self, state: PolymathState) -> dict:
        """
        Execute the RAG cycle for this domain and return a partial state update.

        Steps
        ─────
        1. Retrieve top-k relevant chunks from ChromaDB via similarity search.
        2. Format the retrieved chunks into a numbered context block.
        3. Build the full prompt (system prompt + context + question).
        4. Invoke the LLM and extract the answer string.
        5. Deduplicate citations from document metadata.
        6. Return partial state with: answer, citations, context_docs, agent_trace.

        Error handling
        ──────────────
        If retrieval or generation fails, the agent returns a graceful error
        message in `answer` and records the failure in `agent_trace` so the
        pipeline always terminates cleanly.
        """
        question: str = state["question"]
        self._log.info("%s %s | Query: %r", self.emoji, self.name, question)
        t_start = time.perf_counter()

        # ── Stage 1: Retrieval ─────────────────────────────────────────────
        try:
            docs = self.vector_store.similarity_search(
                query=question,
                k=self.top_k,
            )
            retrieval_elapsed = time.perf_counter() - t_start
            self._log.info(
                "%s %s | Retrieved %d chunk(s) in %.2fs",
                self.emoji, self.name, len(docs), retrieval_elapsed,
            )
        except Exception as exc:  # noqa: BLE001
            self._log.error(
                "%s %s | Retrieval failed: %s", self.emoji, self.name, exc
            )
            return self._error_state(
                question,
                f"retrieval failure ({type(exc).__name__}: {exc})",
            )

        # ── Stage 2: Context formatting ────────────────────────────────────
        context_block = _format_context(docs)

        # ── Stage 3: Prompt construction ───────────────────────────────────
        filled_prompt = _SPECIALIST_PROMPT_TEMPLATE.format(
            system_prompt=self.system_prompt,
            context=context_block,
            question=question,
        )

        # ── Stage 4: LLM generation ────────────────────────────────────────
        try:
            from langchain_core.messages import HumanMessage

            t_gen = time.perf_counter()
            response = self.llm.invoke([HumanMessage(content=filled_prompt)])
            answer: str = response.content.strip()
            gen_elapsed = time.perf_counter() - t_gen

            self._log.info(
                "%s %s | Answer generated in %.2fs (%d chars)",
                self.emoji, self.name, gen_elapsed, len(answer),
            )
        except Exception as exc:  # noqa: BLE001
            self._log.error(
                "%s %s | Generation failed: %s", self.emoji, self.name, exc
            )
            return self._error_state(
                question,
                f"generation failure ({type(exc).__name__}: {exc})",
                docs=docs,
            )

        # ── Stage 5: Citation extraction ───────────────────────────────────
        citations = _extract_citations(docs)

        # ── Stage 6: Trace entry ───────────────────────────────────────────
        total_elapsed = time.perf_counter() - t_start
        trace_entry = (
            f"[{self.name}]  Retrieved {len(docs)} chunk(s) from ChromaDB.  "
            f"Generated answer in {total_elapsed:.2f}s.  "
            f"Citations: {len(citations)}."
        )

        self._log.info(
            "%s %s | Done. Total: %.2fs", self.emoji, self.name, total_elapsed
        )

        # ── Return partial state update ────────────────────────────────────
        # LangGraph merges this dict into PolymathState automatically.
        # `agent_trace` uses operator.add, so the list is *appended* to the
        # existing trace rather than replacing it.
        return {
            "answer":       answer,
            "citations":    citations,
            "context_docs": docs,
            "agent_trace":  [trace_entry],
        }

    # ── Internal helpers ──────────────────────────────────────────────────

    def _error_state(
        self,
        question:    str,
        reason:      str,
        docs:        list | None = None,
    ) -> dict:
        """Return a graceful partial state update when an unrecoverable error occurs."""
        trace_entry = (
            f"[{self.name}]  ERROR — {reason}.  "
            f"Could not generate answer for: {question!r}"
        )
        return {
            "answer": (
                f"I encountered an internal error while processing your question "
                f"({reason}). Please try again or rephrase your query."
            ),
            "citations":    _extract_citations(docs) if docs else [],
            "context_docs": docs or [],
            "agent_trace":  [trace_entry],
        }
