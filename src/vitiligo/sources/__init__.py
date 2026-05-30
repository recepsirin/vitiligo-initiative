"""Source-specific clients that fetch and normalize external data.

Each submodule exposes a client class and a fetch function that yields
`vitiligo.storage.models.Document` instances. Adding a new source means
adding a new submodule here — the storage layer and ingestion pipeline
stay unchanged.
"""

from __future__ import annotations
