"""Settings for the whole test suite, applied before any module reads them.

The suite exercises the built-in course with fresh accounts, so every account gets it here
(backend/course_scope.py). tests/backend/test_course_scope.py checks the real-student mode, where
only the demo people study the built-in course and everyone else works from their uploads."""

import os

os.environ.setdefault("LODESTAR_BUILT_IN_COURSE", "all")
