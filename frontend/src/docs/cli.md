# CLI & Workflow

The `axi` CLI wires extraction, promotion, and querying. Key commands:

## Project setup
- Scaffold a project: `axi scaffold` (creates `axi.yml`, rules, glossary, overrides, metadata_store).
- Generate stubs: `axi generate metric <name> --entity <entity>`, `axi generate dimension <name> --entity <entity>`, `axi generate glossary <term>`, `axi generate rule promotion`.

## Extraction & promotion
- Run extraction with dbt-aware defaults: `axi extract` (auto-detects compiled models from `axi.yml` or `target/compiled/<project>`).
- dbt helpers: `axi dbt scan` (compile + extract), `axi dbt manifest <path>` (load manifest), `axi dbt describe <model>`.
- Promotion dashboard data lives in `metadata_store/` and is exposed at `/api/promotion`.

## Querying
- Generate semantic SQL: `axi query --metric <metric> --dims country,date --filters "country=US"`
- Snowflake execution: `axi query --run` executes via `SnowflakeRunner`.
- Time intelligence & optimization flags are also available under `axi metrics sql`.
- Saved queries (YAML-backed):
  - Files live in `axi/queries/<id>.yml`.
  - API: `GET/POST/DELETE /api/saved_queries`, `POST /api/saved_queries/{id}/run` (supports override filters/limit).
  - UI: save/load/run in the Query Console; browse at `/saved-queries`.

## Glossary & cache
- Glossary: `axi glossary generate` and `axi glossary search <term>`.
- Cache inspection: `axi cache show` / `axi cache clear [--metric ...]`.

## Debugging
- Set `AXI_DEBUG=true` to log scanner decisions and dbt detection.
- `axi extract --debug-models` lists discovered models without extracting.
- Full graph API is gated by `AXI_DEBUG=1`; otherwise use filtered/local graph endpoints.
