"""
agents/router.py
─────────────────────────────────────────────────────────────────────────────
Polymath.ai — Phase 3: Domain Classification Router Node

Responsibilities
────────────────
1.  Receives the raw user question from PolymathState.
2.  Calls an LLM via `with_structured_output` to classify the question into
    one of four CS domains — guaranteed structured output, no regex parsing.
3.  Returns a partial state update with:
        - domain       → string key consumed by the graph's conditional edge
        - agent_trace  → one-line audit entry appended to the running log

Domain taxonomy
───────────────
  compiler_theory   Lexical analysis, parsing, ASTs, IRs, three-address code,
                    CFGs, data-flow analysis, optimization passes, register
                    allocation, code generation.
  algorithms        Sorting, searching, graph algorithms, dynamic programming,
                    greedy strategies, amortized analysis, complexity proofs.
  theory_of_comp    DFA/NFA, context-free grammars, pushdown automata, Turing
                    machines, decidability, P/NP, reductions, complexity classes.
  general_cs        Catch-all for OS, networking, databases, software engineering,
                    or any question that doesn't fit the above domains.

Error contract
──────────────
Any exception during LLM invocation or Pydantic validation is caught, logged,
and resolved by silently defaulting to "general_cs" so the pipeline never
stalls.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, Field

from agents.state import PolymathState

log = logging.getLogger("polymath.router")

# ─────────────────────────────────────────────────────────────────────────────
# Structured output schema
# ─────────────────────────────────────────────────────────────────────────────

# The four valid domain keys — must match the LangGraph conditional edge map
# in orchestrator.py exactly.
DomainLiteral = Literal[
    "compiler_theory",
    "algorithms",
    "theory_of_comp",
    "general_cs",
]


class DomainClassification(BaseModel):
    """
    Structured classification output produced by the Router LLM call.

    Attributes
    ----------
    domain:
        One of the four recognised CS domains.  This value is used directly
        as the key in the LangGraph conditional edge dispatch — typos would
        cause a routing failure, so constrained via Literal.
    confidence:
        Router's self-reported certainty in [0.0, 1.0].  Persisted in the
        agent_trace for observability; does not affect routing logic itself.
    reasoning:
        A one-sentence justification.  Surfaced in debug logs so engineers
        can diagnose mis-classifications without re-running the query.
    """

    domain: DomainLiteral = Field(
        ...,
        description=(
            "The CS domain that best matches the question. "
            "Must be exactly one of: 'compiler_theory', 'algorithms', "
            "'theory_of_comp', 'general_cs'."
        ),
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score for this classification in the range [0.0, 1.0].",
    )
    reasoning: str = Field(
        ...,
        description="One-sentence explanation of why this domain was chosen.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Classification prompt
# ─────────────────────────────────────────────────────────────────────────────

_ROUTER_SYSTEM_PROMPT = """\
You are a domain classification expert for a computer-science educational system.

Your ONLY job is to classify the user's question into exactly ONE of these domains:

  • compiler_theory  — covers: lexical analysis, parsing, abstract syntax trees,
                       intermediate representations, three-address code, control-flow
                       graphs, data-flow analysis, optimization passes, register
                       allocation, and code generation.

  • algorithms       — covers: sorting, searching, graph algorithms (BFS, DFS,
                       Dijkstra, Bellman-Ford, MSTs), dynamic programming, greedy
                       algorithms, amortized analysis, and time/space complexity.

  • theory_of_comp   — covers: finite automata (DFA/NFA), regular expressions,
                       context-free grammars, pushdown automata, Turing machines,
                       decidability, P vs NP, NP-completeness, and reductions.

  • general_cs       — everything else: operating systems, networking, databases,
                       software engineering, system design, or questions spanning
                       multiple domains.

Rules:
- Choose the MOST specific domain that fits.
- If the question spans multiple domains, choose the PRIMARY focus.
- When genuinely uncertain, default to 'general_cs'.
- Your response MUST conform to the required JSON schema — do not add extra fields.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Router node
# ─────────────────────────────────────────────────────────────────────────────

def router_node(state: PolymathState, llm) -> dict:
    """
    LangGraph node: classifies the user question into a CS domain.

    Parameters
    ----------
    state:
        Current graph state.  Only `state["question"]` is consumed.
    llm:
        An initialised `ChatGoogleGenerativeAI` (or any LangChain chat model)
        that supports `.with_structured_output()`.

    Returns
    -------
    dict
        Partial state update with keys `domain` and `agent_trace`.
        LangGraph merges this into the full state automatically.

    Raises
    ------
    Never raises.  All exceptions are caught and resolved via fallback to
    'general_cs' so the graph always continues to the next node.
    """
    question: str = state["question"]
    log.info("Router | Classifying question: %r", question)

    # ── Structured LLM call ───────────────────────────────────────────────
    try:
        structured_llm = llm.with_structured_output(DomainClassification)

        classification: DomainClassification = structured_llm.invoke(
            [
                {"role": "system", "content": _ROUTER_SYSTEM_PROMPT},
                {"role": "user",   "content": f"Question: {question}"},
            ]
        )

        domain: str      = classification.domain
        confidence: float = classification.confidence
        reasoning: str   = classification.reasoning

        log.info(
            "Router | Domain=%r  Confidence=%.2f  Reasoning=%r",
            domain,
            confidence,
            reasoning,
        )

        trace_entry = (
            f"[Router]  Classified query into domain '{domain}'  "
            f"(Confidence: {confidence:.2f})  —  {reasoning}"
        )

    except Exception as exc:  # noqa: BLE001
        # Graceful degradation: any LLM / validation error falls back to
        # the general-purpose agent so the user still gets an answer.
        log.warning(
            "Router | Classification failed (%s: %s). "
            "Defaulting to 'general_cs'.",
            type(exc).__name__,
            exc,
        )
        domain = "general_cs"
        trace_entry = (
            f"[Router]  Classification error ({type(exc).__name__}). "
            f"Defaulted to domain 'general_cs'."
        )

    # ── Return partial state update ───────────────────────────────────────
    # `agent_trace` is a new list here; LangGraph's operator.add reducer
    # will *concatenate* it with the existing trace — not replace it.
    return {
        "domain": domain,
        "agent_trace": [trace_entry],
    }
