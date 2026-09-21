"""News-source adapters: GDELT, NewsAPI, GNews, Mediastack and Currents.

Every adapter implements the same ``NewsSource`` Protocol and shares one ``httpx`` client
with an RFC 9111 cache (``hishel``). They land with phase 2.
"""
