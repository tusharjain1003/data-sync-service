from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FetchResult:
    records: list[dict[str, Any]] = field(default_factory=list)
    cursor: str | None = None


class SyncConnector(ABC):
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Human-readable name for this source (e.g. 'hubspot_crm')."""

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Category of source (e.g. 'crm', 'calendar', 'payments')."""

    @abstractmethod
    async def fetch_full(self) -> FetchResult:
        """Perform a full fetch of all records from the source."""

    @abstractmethod
    async def fetch_incremental(self, cursor: str | None) -> FetchResult:
        """Fetch only records that changed since the given cursor."""
