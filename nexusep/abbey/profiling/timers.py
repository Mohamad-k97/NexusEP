"""
Simple ABBEY timing utilities.

No pandas dependency.
No external profiler dependency.
Safe for normal runs.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List
import time


@dataclass
class TimerStat:
    name: str
    total_seconds: float = 0.0
    call_count: int = 0

    def add(self, elapsed_seconds: float) -> None:
        self.total_seconds += float(elapsed_seconds)
        self.call_count += 1

    @property
    def seconds_per_call(self) -> float:
        if self.call_count <= 0:
            return 0.0

        return self.total_seconds / float(self.call_count)

    def to_dict(self) -> Dict[str, float]:
        return {
            "name": self.name,
            "total_seconds": self.total_seconds,
            "call_count": self.call_count,
            "seconds_per_call": self.seconds_per_call,
        }


@dataclass
class AbbeyTimer:
    enabled: bool = True
    stats: Dict[str, TimerStat] = field(default_factory=dict)

    @contextmanager
    def measure(self, name: str):
        if not self.enabled:
            yield
            return

        start = time.perf_counter()

        try:
            yield
        finally:
            elapsed = time.perf_counter() - start

            if name not in self.stats:
                self.stats[name] = TimerStat(name=name)

            self.stats[name].add(elapsed)

    def summary_rows(self, root_name=None):
        if root_name is not None and root_name in self.stats:
            denominator = self.stats[root_name].total_seconds
        else:
            denominator = sum(
                stat.total_seconds
                for stat in self.stats.values()
            )

        rows = []

        for name, stat in sorted(
            self.stats.items(),
            key=lambda item: item[1].total_seconds,
            reverse=True,
        ):
            row = stat.to_dict()
            row["share_percent"] = (
                100.0 * stat.total_seconds / denominator
                if denominator > 0.0
                else 0.0
            )
            rows.append(row)

        return rows
    def print_summary(
        self,
        title="ABBEY timing summary",
        root_name=None,
    ):
        rows = self.summary_rows(root_name=root_name)

        print("\n" + title)

        if not rows:
            print("  no timing records")
            return

        if root_name is not None:
            print("  denominator:", root_name)

        for row in rows:
            print(
                "  "
                + str(row["name"]).ljust(45)
                + " total="
                + "{:.3f}".format(row["total_seconds"]).rjust(10)
                + "s"
                + " calls="
                + str(row["call_count"]).rjust(8)
                + " per_call="
                + "{:.6f}".format(row["seconds_per_call"]).rjust(12)
                + "s"
                + " share="
                + "{:.1f}".format(row["share_percent"]).rjust(6)
                + "%"
            )