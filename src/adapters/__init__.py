"""Read-only data adapters (Phase 8). No OPC, Modbus, serial, network or database-write code lives here (tested).
Names are imported lazily so `python -m src.adapters.<module>` runs without import-order warnings."""


def __getattr__(name):
    if name in ("ReadOnlySource", "SourceResult"):
        from src.adapters import base
        return getattr(base, name)
    if name == "CsvExportSource":
        from src.adapters.csv_export import CsvExportSource
        return CsvExportSource
    if name == "SyntheticSource":
        from src.adapters.synthetic import SyntheticSource
        return SyntheticSource
    raise AttributeError(name)
