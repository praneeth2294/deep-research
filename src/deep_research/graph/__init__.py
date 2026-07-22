"""LangGraph assembly: state, builder, and nodes.

`state.py` — the shared ResearchState (TypedDict + reducers).
`builder.py` — wires nodes, edges, interrupts, and the checkpointer.
`nodes/` — one module per node; each implements exactly one deck pattern.
"""
