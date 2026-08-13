# Source manifests

Validation category: **verification** (data provenance)

Store one JSON manifest per retrieved external source. File names should match
the stable `source_id`. Placeholder checksums, guessed licenses, and candidate
URLs are not evidence and must not be registered.

The authoritative contract is
`nexusep.validation_data.registry.DataSourceRecord`; print its JSON Schema with:

```powershell
.venv\Scripts\python.exe -m nexusep.validation_data.registry schema
```
