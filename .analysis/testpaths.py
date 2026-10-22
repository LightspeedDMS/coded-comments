"""Shared test/fixture path classifier for corpus statistics (analysis tooling only)."""

import re
from pathlib import PurePosixPath

TEST_DIRS = {"test", "tests", "__tests__", "fixtures", "testdata", "test_data", "spec", "e2e"}
# Lowercase basename: test_x.py, x_test.go, x_tests.rs, x_tests_family.rs, a.test.ts, a.spec.js
LOWER_NAME = re.compile(r"(^test_|_tests?(_\w+)?\.\w+$|\.(test|spec)\.\w+$)")
# Case-sensitive: FooTest.java, JobTests.cs (not Latest.java)
CAMEL_NAME = re.compile(r"[a-z0-9]Tests?\.(java|cs)$")


def is_test_path(path):
    p = PurePosixPath(path)
    if any(part.lower() in TEST_DIRS for part in p.parts[:-1]):
        return True
    return bool(LOWER_NAME.search(p.name.lower()) or CAMEL_NAME.search(p.name))
