"""Compatibility entry point for the relocated v0.1 object runner."""

import runpy


if __name__ == "__main__":
    runpy.run_module("benchmarks.object.v0_1_runner", run_name="__main__")
