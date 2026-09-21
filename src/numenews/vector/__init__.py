"""Qdrant: client, the five collections, payload indexes and hybrid search.

Payload indexes are created before any ingest, and filters go inside ``Prefetch`` in
multi-stage queries. The collections land with phase 3.
"""
