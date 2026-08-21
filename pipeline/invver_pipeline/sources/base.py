"""Source adapters.

Each adapter turns some external location into `RawContract` objects. The
interface is deliberately tiny: `fetch()` for one contract, `discover()` for
sources that can enumerate.

Network access goes through the module-level `http_get` in each adapter so tests
can substitute a fixture without hitting the network.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from collections.abc import Iterator

from ..model import RawContract


class SourceError(RuntimeError):
    pass


def http_get(url: str, timeout: float = 30.0) -> str:
    """Plain GET returning text. Adapters call their own module copy of this so
    a test can monkeypatch one adapter without touching the others."""
    req = urllib.request.Request(url, headers={"User-Agent": "invver-pipeline/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        raise SourceError(f"HTTP {e.code} for {url}") from e
    except urllib.error.URLError as e:
        raise SourceError(f"network error for {url}: {e.reason}") from e


class Source(ABC):
    """A place contracts come from."""

    name: str

    @abstractmethod
    def fetch(self, identifier: str, chain_id: int | None = None) -> RawContract:
        """Pull one contract by address (verified-source adapters) or path
        (repo adapters)."""
        raise NotImplementedError

    def discover(self) -> Iterator[RawContract]:
        """Enumerate contracts this source can offer, newest first.

        Optional — verified-source adapters that need an explicit address raise
        here, repo adapters implement it.
        """
        raise NotImplementedError(
            f"{self.name} cannot enumerate; call fetch() with an identifier"
        )
