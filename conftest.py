from __future__ import annotations

import os
import tempfile
from pathlib import Path


# Force pytest's temp root into a dedicated user-writable directory outside the
# repo and outside the system temp tree. Pytest still creates per-run unique
# subdirectories under this root, so reruns do not collide on one fixed tree.
_USER_TEMP_ROOT = Path.home() / ".forge-agent-pytest-tmp"
_USER_TEMP_ROOT.mkdir(exist_ok=True)

temp_root = str(_USER_TEMP_ROOT)
os.environ["TMPDIR"] = temp_root
os.environ["TEMP"] = temp_root
os.environ["TMP"] = temp_root
tempfile.tempdir = temp_root
