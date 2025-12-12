# Saved Queries & Query API

Saved queries let you define reusable semantic queries in YAML, version them with your project, and run them via UI or API.

## Storage
- Files live at `axi/queries/<id>.yml`.
- `id` must match the filename (slug-like `[a-zA-Z0-9_-]+`).
- Example:
  ```yaml
  id: monthly_revenue_uk
  name: Monthly Revenue (UK)
  description: Total revenue per month for UK customers
  entity: orders
  metrics: [total_revenue]
  dimensions: [month]
  filters:
    - dimension: country
      op: "="
      value: "UK"
  limit: 500
  tags: [finance, exec_dashboard]
  ```

## Backend API
- List: `GET /api/saved_queries`
- Get one: `GET /api/saved_queries/{id}`
- Create/Update: `POST /api/saved_queries` (body = SavedQuery)
- Delete: `DELETE /api/saved_queries/{id}`
- Run: `POST /api/saved_queries/{id}/run`
  - Body (optional):
    ```json
    { "override_filters": [...], "override_limit": 200 }
    ```
  - Returns columns/rows/sql from the semantic engine (same errors as `/api/query/semantic`).
  - Errors include `SAVED_QUERY_NOT_FOUND`, `INVALID_SAVED_QUERY`, semantic join/filter errors, Snowflake auth/connection issues.

## UI Workflow
- Query Console now supports:
  - Saving the current entity/metrics/dimensions/filters/limit (Save Query).
  - Loading saved queries into the console.
  - Running saved queries directly from the sidebar.
- Saved Queries page (`/saved-queries`):
  - List/search by name/id/tag/entity.
  - Quick run, delete, open in console.

## External Consumption
- Use `POST /api/saved_queries/{id}/run` from schedulers, services, or BI tools to pull consistent metrics.
- You can override filters/limit without editing YAML.

## Validation
- YAML is the source of truth. The store validates:
  - `id` matches filename.
  - Entity/metrics exist.
  - Dimensions compatible with metrics (best-effort).
- Broken files are skipped in list; fetching a broken file returns `INVALID_SAVED_QUERY`.
