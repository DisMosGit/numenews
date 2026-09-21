"""numenews — a numerological reading of the news.

The package is layered. ``numerology`` is pure logic with no I/O, ``models`` holds the Pydantic v2
types that cross module boundaries, and ``news``, ``embeddings``, ``vector``, ``agents`` and
``pipeline`` build the reading on top of them, with ``cli`` still to come.

Phases 0 to 6 are implemented so far: configuration, logging, the domain models, the pure numerology
layer, the five news sources behind one Protocol, the vector layer (local embeddings plus the six
Qdrant collections) and the four ``pydantic-ai`` agents, composed by the RAG pipeline of
``numenews.pipeline`` and exposed by the nine MCP tools of ``numenews.mcp``. ``ROADMAP.md`` is the
phase plan.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
