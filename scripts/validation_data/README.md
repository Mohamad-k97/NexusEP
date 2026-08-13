# Validation-data preprocessing

Validation category: **verification** (transformation provenance)

Preprocessing and scientific-analysis scripts belong in a source-specific
subdirectory. Each registered command must be non-interactive and deterministic
under the project lock file. Manifests record the script path and SHA-256 so a
later code change cannot silently alter an existing evidence chain.
