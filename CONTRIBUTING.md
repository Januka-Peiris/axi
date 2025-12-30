# Contributing to AXI

Thank you for your interest in contributing to AXI! We welcome contributions from the community.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/your-username/axi.git
   cd axi
   ```
3. **Install dependencies**:
   ```bash
   make install
   ```

## Development Workflow

### Setup

```bash
# Install all packages (backend, CLI, frontend)
make install

# Start development servers
make dev
```

This starts:
- Backend API at http://localhost:8000
- Frontend UI at http://localhost:5173

### Making Changes

1. Create a new branch:
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. Make your changes and add tests

3. Run tests:
   ```bash
   make test
   ```

4. Run linting:
   ```bash
   # Python
   ruff check backend/ axi-cli/

   # Frontend
   cd frontend && npm run lint
   ```

5. Commit your changes with clear messages

6. Push and submit a Pull Request

### Available Commands

```bash
make help       # Show all available commands
make install    # Install all packages
make dev        # Start development servers
make backend    # Start backend only
make frontend   # Start frontend only
make test       # Run tests
make clean      # Clean build artifacts
make uninstall  # Remove installed packages
```

## Code Style

### Python
- We use `ruff` for linting and formatting
- Follow PEP 8 conventions
- Add type hints to function signatures

### TypeScript/React
- We use `prettier` and `eslint`
- Follow the existing component patterns
- Use TypeScript for all new code

## Project Structure

```
axi/
├── backend/      # Core semantic engine (BSL 1.1)
├── axi-cli/      # CLI tool (MIT)
├── frontend/     # React UI (MIT)
├── docker/       # Docker support
└── examples/     # Demo projects
```

## Pull Request Guidelines

1. Keep PRs focused on a single feature or fix
2. Update documentation if needed
3. Add tests for new functionality
4. Ensure all tests pass
5. Follow the existing code style

## Reporting Issues

If you find a bug or have a feature request:

1. Check existing issues first
2. Open a new issue with:
   - Clear description
   - Steps to reproduce (for bugs)
   - Expected vs actual behavior
   - Environment details

## Code of Conduct

Please be respectful and constructive in all interactions. We're building something together.

## Questions?

- Open a GitHub issue for questions
- Check the documentation in the repo

Thank you for contributing!
