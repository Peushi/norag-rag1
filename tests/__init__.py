"""Test package setup: tests never write to the user's real trace database.

Some tests run the real question or indexing pipeline without patching the
trace store, and each full run used to add 14 fake traces to
.bakefix/traces.sqlite3, which the metrics page then counted as real usage.
This runs before any test module (and before backend.tracing is imported),
so every trace a test does not redirect itself goes to a throwaway file.
"""

import atexit
import os
import shutil
import tempfile

_TRACE_DIR = tempfile.mkdtemp(prefix="bakefix-test-traces-")
os.environ["BAKEFIX_TRACE_DB"] = os.path.join(_TRACE_DIR, "traces.sqlite3")
atexit.register(shutil.rmtree, _TRACE_DIR, ignore_errors=True)
