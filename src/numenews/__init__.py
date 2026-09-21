"""numenews — a numerological reading of the news.

The package is layered. ``numerology`` is pure logic with no I/O, ``models`` holds the
Pydantic v2 types that cross module boundaries, and ``news``, ``embeddings``, ``vector``,
``agents``, ``mcp`` and ``cli`` build the pipeline on top of them.

Phases 0 to 2 are implemented so far: configuration, logging, the domain models, the pure
numerology layer and the five news sources behind one Protocol. ``ROADMAP.md`` is the phase plan.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
