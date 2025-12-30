# AXI Installation Guide

## Quick Install

From the project root, run:
```bash
make install
```

This single command will:
- Install the backend package (`axi-semantic`) in editable mode
- Install the CLI package (`axi-cli`) in editable mode
- Install all frontend dependencies
- Make the `axi` and `axi-api` commands available globally

## Verify Installation

Check that the CLI is installed:
```bash
axi --help
```

Check installed packages:
```bash
pip list | grep axi
```

You should see:
- `axi-semantic==0.1.0`
- `axi-cli==0.1.0`

## Manual Installation

If you prefer step-by-step installation:

```bash
# 1. Install build tools
python -m pip install --upgrade pip hatchling

# 2. Install backend package
python -m pip install -e backend

# 3. Install CLI package
python -m pip install -e axi-cli

# 4. Install frontend dependencies
cd frontend && npm install
```

## Uninstall

To remove all AXI packages:
```bash
make uninstall
```

## Clean Build Artifacts

To clean up build artifacts and caches:
```bash
make clean
```

## Development Workflow

After installation, start the development environment:

```bash
# Start both backend and frontend
make dev

# Or individually:
make backend    # API server on http://localhost:8000
make frontend   # UI on http://localhost:5173
```

## Troubleshooting

### Permission Errors
If you get permission errors during install, use:
```bash
python -m pip install --user -e backend
python -m pip install --user -e axi-cli
```

### Command Not Found
If `axi` command is not found after install:
1. Check your Python bin directory is in PATH
2. Try running: `python -m axi_cli.main --help`
3. Or reinstall: `make uninstall && make install`

### Build Errors
If you encounter build errors:
1. Clean existing artifacts: `make clean`
2. Ensure you have Python 3.9+: `python --version`
3. Try manual installation steps above

## Environment Variables

Customize development settings:
```bash
BACKEND_HOST=0.0.0.0 BACKEND_PORT=9000 FRONTEND_PORT=3000 make dev
```

## What Gets Installed

The monorepo contains three main packages:

1. **Backend** (`backend/`): Core semantic engine
   - Package name: `axi-semantic`
   - License: BSL 1.1
   - Command: `axi-api`

2. **CLI** (`axi-cli/`): Command-line interface
   - Package name: `axi-cli`
   - License: MIT
   - Command: `axi`

3. **Frontend** (`frontend/`): React UI
   - Not a Python package
   - Uses npm for dependencies

All packages are installed in **editable mode** (`-e`), meaning:
- Changes to source code take effect immediately
- No need to reinstall after code changes
- Perfect for development

## Next Steps

After installation:
1. Review the main [README.md](README.md) for features and usage
2. Check available commands: `make help`
3. Start developing: `make dev`
4. Run the demo: `axi extract examples/demo && axi ui`

## Getting Help

- Run `make help` for all available commands
- Run `axi --help` for CLI usage
- Check the [README.md](README.md) for detailed documentation
