import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


import shutil  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _keep_effect_model_bytes():
    """Phase 4 tests refit and re-dump models/effect_model.joblib; restore the committed bytes afterwards."""
    p = Path(__file__).resolve().parents[1] / "models" / "effect_model.joblib"
    keep = p.read_bytes() if p.exists() else None
    yield
    if keep is not None:
        p.write_bytes(keep)


@pytest.fixture(autouse=True)
def _isolated_logs(tmp_path, monkeypatch):
    """Operator log and audit log go to a temp folder in every test (never the real data/ files)."""
    monkeypatch.setenv("HEATER_OPLOG_DB", str(tmp_path / "op.db"))
    monkeypatch.setenv("HEATER_AUDIT_DB", str(tmp_path / "audit.db"))
