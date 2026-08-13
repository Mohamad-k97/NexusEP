# Phase 1.2 — reproducible Python environment

Validation category: **verification** (environment provenance only)

## Supported interpreter

The supported line is **CPython 3.12.x, 64-bit**. `pyproject.toml` enforces
`>=3.12,<3.13`. The recovered environment was created and verified with:

```text
Python 3.12.2 (64-bit)
Windows-11-10.0.26200-SP0
pip 24.0
```

Python 3.14 is not used for recovery or verification.

## Clean bootstrap (PowerShell)

From a fresh clone:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip==24.0
.\.venv\Scripts\python.exe -m pip install -c requirements\constraints-py312.txt -e ".[dev,benchmark]"
```

The build backend is pinned to `setuptools==80.9.0`. The constraints file pins
every resolved runtime, GIS/scientific, development, and benchmark dependency.
Numba and psutil are in the optional `benchmark` extra. The constraints file
SHA-256 is
`d90e1e0b1985859da9354d0a9d64e84a1bffc092bd52d231eb864f0625dbcc37`.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import nexusep, numpy, pandas, pytest; print(numpy.__version__, pandas.__version__, pytest.__version__)"
.\.venv\Scripts\python.exe -m pytest -q
```

Verified again on 2026-08-06 after adding benchmark RSS measurement support:

- `pip check`: `No broken requirements found.`
- imports: nexusep, NumPy, pandas, pytest, GeoPandas, Shapely, pyproj,
  rasterio, SciPy, Matplotlib, lxml, Pydantic, PyArrow, Numba, and psutil
  succeeded.
- full suite: `53 passed in 17.32s` (20.6 s process wall time).

Key resolved versions are NumPy 2.4.6, pandas 3.0.5, pytest 9.1.1,
GeoPandas 1.1.4, Shapely 2.1.2, pyproj 3.7.2, rasterio 1.5.0, SciPy 1.18.0,
Matplotlib 3.11.1, PyArrow 25.0.0, Numba 0.66.0, and psutil 7.2.2. The complete
authoritative list is `requirements/constraints-py312.txt`.

The environment contains 46 installed project/runtime/development/benchmark
packages matching the constraints. `setuptools==80.9.0` is the 47th pinned
entry and is supplied to pip's isolated build environment, so it is not
retained as an importable package in `.venv`. `pip check` is clean.

Matplotlib is explicitly declared because production output modules import it.
The output exporter selects the non-interactive `Agg` backend so verification
does not depend on a working Tk installation or display server.
