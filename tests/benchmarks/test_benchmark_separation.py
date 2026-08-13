"""Verification that benchmark scripts and correctness tests remain separate."""

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.benchmark
VALIDATION_CATEGORY = "verification"


def test_benchmark_implementations_live_outside_production_source() -> None:
    root = Path(__file__).resolve().parents[2]
    benchmark_files = list((root / "benchmarks").rglob("*.py"))
    assert benchmark_files
    assert all((root / "nexusep") not in path.parents for path in benchmark_files)


def test_benchmark_tests_do_not_use_narrow_timing_assertions() -> None:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    timing_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Name) and node.func.id == "timeit")
            or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "perf_counter"
            )
        )
    ]
    assert timing_calls == []
