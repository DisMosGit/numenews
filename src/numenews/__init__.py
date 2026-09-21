"""numenews — a numerological reading of the news.

The package is layered. ``numerology`` is pure logic with no I/O, ``models`` holds the
Pydantic v2 types that cross module boundaries, and ``news``, ``embeddings``, ``vector``,
``agents``, ``mcp`` and ``cli`` build the pipeline on top of them.

Only phase 0 (skeleton) is implemented so far; ``ROADMAP.md`` is the phase plan.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
