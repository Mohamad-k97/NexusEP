# Dependency constraints

`constraints-py312.txt` is the exact CPython 3.12 resolution verified on
Windows. Keep direct dependency intent in `pyproject.toml`; use this file only
to reproduce the validated resolution.

Bootstrap with:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip==24.0
.\.venv\Scripts\python.exe -m pip install -c requirements\constraints-py312.txt -e ".[dev,benchmark]"
```
