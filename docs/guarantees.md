# AXI Operational Guarantees

This document describes AXI's behavioral guarantees for teams embedding AXI in CI/CD pipelines.

## Determinism

AXI guarantees deterministic outputs. Given identical inputs:

- The same SQL files produce byte-identical metadata JSON
- File processing order does not affect output
- No timestamps, random UUIDs, or non-deterministic values appear in semantic artifacts

**Implementation details:**
- All filesystem iteration (`os.walk`, `glob.glob`) is sorted
- All JSON/YAML serialization uses `sort_keys=True`
- Metadata schema includes `schema_version` for forward compatibility
- IDs are derived from content hashes, not random generation

**What this enables:**
- Git diff on metadata files
- Caching based on input hash
- Reproducible builds across environments

**What is NOT deterministic:**
- Run summary timestamps (`started_at`, `completed_at`) — these are allowed in run summaries, not semantic artifacts
- Log output ordering

## Exit Code Contract

AXI uses exit codes strictly. The CLI will never return exit 0 if any item failed.

| Code | Constant | When Used |
|------|----------|-----------|
| 0 | `SUCCESS` | All items processed without error |
| 1 | `GENERAL_ERROR` | Unexpected runtime exception |
| 2 | `CONFIG_ERROR` | Invalid `axi.yml`, missing required fields, malformed YAML |
| 3 | `VALIDATION_ERROR` | Invalid SQL syntax, schema violations |
| 4 | `NOT_FOUND` | Specified path does not exist |
| 5 | `EXTRACTION_ERROR` | One or more models failed to extract |
| 6 | `CONNECTION_ERROR` | Database or warehouse connection failed |

### Partial Success = Exit 5

If 99 models succeed and 1 fails, AXI returns exit code 5 (not 0).

**Rationale**: Partial metadata is potentially more dangerous than no metadata. A dashboard querying "all metrics" would silently miss the failed model. CI/CD pipelines should fail explicitly.

**If you need partial success to pass CI:**
1. Use `--summary` to write JSON, then parse it in your pipeline
2. Implement custom logic based on failure counts
3. Do not expect AXI to make this decision for you

## Run Summary Contract

When `--summary <file>` is specified, AXI writes a JSON file with this schema:

```json
{
  "schema_version": "1.0",
  "command": "extract",
  "status": "partial_success",
  "exit_code": 5,
  "counts": {
    "scanned": 100,
    "processed": 95,
    "skipped": 2,
    "failed": 3
  },
  "failures": [
    {"item": "models/broken.sql", "error": "Parse error at line 42"}
  ],
  "skipped": [
    {"item": "models/staging/temp.sql", "reason": "excluded by promotion rule"}
  ],
  "started_at": "2025-01-15T10:00:00Z",
  "completed_at": "2025-01-15T10:00:05Z"
}
```

### Status Values

| Status | Meaning |
|--------|---------|
| `success` | All items processed, none failed |
| `partial_success` | Some items processed, some failed |
| `failure` | Zero items processed successfully |
| `error` | Command failed before processing items |

### Counts Semantics

- `scanned`: Total files matching promotion rules
- `processed`: Successfully extracted and written
- `skipped`: Excluded by rules OR lacking semantic content (no GROUP BY)
- `failed`: Parse errors or extraction exceptions

## What Breaks CI

These conditions cause non-zero exit:

| Condition | Exit Code | Recoverable? |
|-----------|-----------|--------------|
| Any model fails to parse | 5 | Fix SQL syntax |
| `axi.yml` is malformed | 2 | Fix configuration |
| Specified path doesn't exist | 4 | Check path |
| dbt manifest missing (without `--no-dbt`) | 2 | Run `dbt compile` |
| Snowflake connection fails (when required) | 6 | Check credentials |

## What Does NOT Break CI

These conditions result in exit 0:

| Condition | Behavior |
|-----------|----------|
| Zero models match promotion rules | Success (0 scanned, 0 processed) |
| All models skipped due to no grain | Success (N scanned, 0 processed, N skipped) |
| Empty SQL directory | Success (0 scanned) |
| No metrics in any model | Success (models extracted, just no metrics) |

## Dry Run Guarantees

`axi extract --dry-run` guarantees:

- **No files written** — `metadata_store/` is not modified
- **Full validation** — All parsing and promotion rules are applied
- **Same exit codes** — Failures return non-zero
- **Summary available** — `--summary` works with `--dry-run`

Use dry run to validate changes before committing metadata.

## Quiet Mode Guarantees

`axi extract --quiet` guarantees:

- **No stdout on success** — Only stderr receives output
- **Errors still printed** — Parse failures go to stderr
- **Exit codes unchanged** — Non-zero on failure

Combine with `--summary` for machine-readable output in CI:

```bash
axi extract --quiet --summary summary.json
if [ $? -ne 0 ]; then
  cat summary.json | jq '.failures'
  exit 1
fi
```

## Schema Versioning

Metadata files include `schema_version` (currently `"1.0"`).

- **MAJOR bump**: Breaking changes requiring migration
- **MINOR bump**: Additive changes (new optional fields)

AXI does not automatically migrate old metadata. If schema version changes, re-run extraction.

## Inference Transparency

When AXI infers semantics (FK relationships, grain), the inference is:

1. **Marked in output**: `join_type: "INFERRED_FK"`, `inferred: true`
2. **Not used by default**: Query generation ignores inferred relationships
3. **Logged**: Inference events appear in debug output

To audit inference:

```bash
# Find all inferred relationships
grep -r "INFERRED_FK" metadata_store/models/

# Check grain sources
grep -r '"source": "entity_pk"' metadata_store/models/
```
