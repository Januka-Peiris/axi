# Business Glossary

AXI generates and serves a glossary so business terms stay aligned with the semantic layer.

## Sources

- **Glossary YAML** in `glossary/` (created by `axi generate glossary <term>`).
- **Overrides** in `overrides/` can enrich entity names/descriptions.
- **Extraction**: entities, dimensions, and metrics contribute friendly names and relationships.

## Commands

- Generate glossary JSON/SQLite: `axi glossary generate`
- Search terms: `axi glossary search "<query>"`

## UI

- Glossary entries appear in the UI with related entities/metrics.
- Entity detail pulls dimension metadata (pruned or full via `include_pruned` flag in API).

## Tips

- Keep definitions short and actionable; link to owners via tags.
- Align glossary terms with metric/entity names to simplify navigation.
