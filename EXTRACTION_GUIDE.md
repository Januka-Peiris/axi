# AXI Extraction Guide - Promote Everything

## Quick Start: Extract Everything from Target Folder

To extract and promote **everything** from your compiled dbt models:

### Option 1: Empty Include Rules (Promotes Everything)

Create or update `axi.yml`:

```yaml
project: your_project_name
dbt:
  compiled_path: target/compiled/your_project_name/models

promotion:
  include:
    folders: []    # Empty = promote everything
    tags: []        # Empty = promote everything
  exclude:
    folders: []     # Optional: exclude specific paths
    tags: []        # Optional: exclude specific tags
```

### Option 2: Wildcard Pattern (Promotes Everything)

```yaml
project: your_project_name
dbt:
  compiled_path: target/compiled/your_project_name/models

promotion:
  include:
    folders: ["**"]  # Match all files recursively
    tags: []
  exclude:
    folders: []
    tags: []
```

## How to Run Extraction

### Method 1: Using `axi extract` (Recommended)

```bash
# If you have compiled_path in axi.yml, just run:
axi extract

# Or specify the path explicitly:
axi extract target/compiled/your_project_name/models
```

### Method 2: Using `axi dbt scan` (dbt projects only)

```bash
# Automatically detects dbt project and uses compiled path
axi dbt scan
```

## Verify Extraction

After extraction, check what was extracted:

```bash
# List all metrics
axi metrics list

# Check the UI
axi ui
# Then visit http://localhost:3000
```

## Debug Mode

To see what's being scanned and promoted:

```bash
# See all discovered models (without extracting)
axi extract --debug-models

# See detailed extraction logs
axi extract --debug
```

## Troubleshooting

### Nothing shows up in UI?

1. **Check promotion rules**: Make sure `include.folders` is empty or contains `["**"]`
2. **Verify compiled path exists**: Run `dbt compile` first
3. **Check extraction output**: Look for "Models scanned" and "Models parsed successfully"
4. **Verify SQL root**: The extraction should show the SQL root path being used

### Models are being skipped?

Enable debug mode to see which models are skipped:
```bash
AXI_DEBUG=true axi extract --debug
```

Look for `[SKIP] Not promoted: <path>` messages.

## Understanding Promotion Rules

- **Empty include rules** = Promote everything (default for raw SQL)
- **Include rules specified** = Only promote matching files
- **Exclude rules** = Always take precedence (exclude even if included)

### Path Matching

Paths are relative to the SQL root (compiled path). Examples:
- SQL root: `target/compiled/project/models`
- File: `target/compiled/project/models/marts/revenue.sql`
- Relative path for promotion: `marts/revenue.sql`

### Pattern Examples

```yaml
include:
  folders:
    - "**"              # Match everything recursively
    - "marts/**"        # Match all files in marts/ and subdirectories
    - "models/*"        # Match all files directly in models/ (not subdirs)
    - "staging/orders"  # Match specific file or directory
```

