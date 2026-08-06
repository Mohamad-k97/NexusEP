"""Compatibility entry point for the relocated v0.2 object runner."""

import runpy


if __name__ == "__main__":
    runpy.run_module("benchmarks.object.v0_2_runner", run_name="__main__")
