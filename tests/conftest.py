"""Point the test suite at the workspace copy when one exists.

DOJO_TARGET=reference forces the clean implementation (used by `dojo verify`).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
target = os.environ.get("DOJO_TARGET")
if target is None:
    target = "workspace" if (ROOT / "workspace" / "supportdesk").exists() else "reference"
sys.path.insert(0, str(ROOT / target))

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _announce_target():
    print(f"\n[dojo] testing supportdesk from {target}/")
