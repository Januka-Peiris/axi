# Publishing AXI to PyPI

## Quick Check: Is it already published?

```bash
# Check if package exists on PyPI
curl -s "https://pypi.org/pypi/axi-semantic/json" | grep -o '"version":"[^"]*"' | head -1

# Or visit in browser:
# https://pypi.org/project/axi-semantic/
```

If you get `{"message": "Not Found"}`, the package is **not published yet**.

## Prerequisites

1. **PyPI Account**: Create one at https://pypi.org/account/register/
2. **API Token**: 
   - Go to https://pypi.org/manage/account/token/
   - Create a new API token (scope: "Entire account" or project-specific)
   - Save it securely (you'll only see it once)

3. **Install build tools**:
   ```bash
   pip install --upgrade build twine
   ```

## Publishing Steps

### Option 1: Use the Script (Recommended)

```bash
# Test on TestPyPI first (recommended)
./scripts/publish_to_pypi.sh test

# Then publish to production PyPI
./scripts/publish_to_pypi.sh prod
```

### Option 2: Manual Commands

#### 1. Check Current Version
```bash
cd backend
grep "version" pyproject.toml
```

#### 2. Build the Package
```bash
cd backend
python -m build
# This creates: dist/axi-semantic-0.1.0.tar.gz and dist/axi_semantic-0.1.0-py3-none-any.whl
```

#### 3. Check the Build
```bash
# Verify files
ls -lh dist/

# Check package contents (optional)
tar -tzf dist/axi-semantic-*.tar.gz | head -20
```

#### 4. Upload to TestPyPI (Recommended First)
```bash
# Upload to TestPyPI (requires separate account at test.pypi.org)
twine upload --repository testpypi dist/*

# Test install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ axi-semantic
```

#### 5. Upload to Production PyPI
```bash
# Upload to PyPI (production)
twine upload dist/*

# You'll be prompted for:
# - Username: __token__
# - Password: <your-api-token>
```

## Using Environment Variables (More Secure)

Instead of entering credentials interactively:

```bash
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-<your-api-token>

twine upload dist/*
```

Or create `~/.pypirc`:
```ini
[pypi]
username = __token__
password = pypi-<your-api-token>
```

## Updating Version

Before publishing a new version:

1. **Update version in `backend/pyproject.toml`**:
   ```toml
   version = "0.1.1"  # Increment as needed
   ```

2. **Commit and tag**:
   ```bash
   git add backend/pyproject.toml
   git commit -m "Bump version to 0.1.1"
   git tag v0.1.1
   git push origin main --tags
   ```

3. **Build and publish**:
   ```bash
   cd backend
   python -m build
   twine upload dist/*
   ```

## Automated Publishing (GitHub Actions)

You already have a workflow at `.github/workflows/publish-python.yml` that:
- Triggers on GitHub releases
- Builds both backend and CLI packages
- Publishes to PyPI using `PYPI_API_TOKEN` secret

To use it:
1. Add `PYPI_API_TOKEN` secret in GitHub repo settings
2. Create a GitHub release (this triggers the workflow)

## Verification

After publishing, verify:

```bash
# Check package on PyPI
curl -s "https://pypi.org/pypi/axi-semantic/json" | python -m json.tool

# Install and test
pip install axi-semantic
python -c "import axi; print(axi.__version__)"  # If you add __version__
```

## Troubleshooting

### "Package already exists"
- PyPI doesn't allow overwriting existing versions
- Increment version in `pyproject.toml` and rebuild

### "Invalid distribution"
- Check `pyproject.toml` syntax
- Ensure `packages = ["axi"]` matches your actual package structure

### "Authentication failed"
- Verify API token is correct
- Use `__token__` as username, not your PyPI username
- Token should start with `pypi-`

## Package Name Availability

Your package name is: **`axi-semantic`**

Check availability:
- https://pypi.org/project/axi-semantic/ (currently not found = available)
