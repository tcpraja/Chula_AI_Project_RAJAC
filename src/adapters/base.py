"""Read-only data-source interface. There is deliberately NO write, publish, set or connect-to-plant method (CLAUDE.md rule 3).

A source returns a frame in the tool's internal raw schema (same columns as data/raw_synthetic/synthetic_heater_c_5min.csv)
plus metadata. SYNTHETIC code path only in this repository; site tag maps are filled by the site, never from this repo.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class SourceResult:
    df: pd.DataFrame
    meta: dict = field(default_factory=dict)      # source kind, row count, unavailable columns, missing site tags (names only)


class ReadOnlySource(ABC):
    """Interface: read() and describe() only."""

    kind = "abstract"

    @abstractmethod
    def read(self) -> SourceResult:
        """Return rows in the internal raw schema. Must not modify the source."""

    def describe(self) -> dict:
        return {"kind": self.kind, "read_only": True}
