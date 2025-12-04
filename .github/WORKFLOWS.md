# GitHub Actions Setup

This project uses GitHub Actions for CI/CD automation. Three workflows have been configured:

## Workflows

### 1. CI (`ci.yml`)
**Trigger**: On push/PR to `master` or `main` branches

**What it does**:
- Runs tests across Python 3.9, 3.10, 3.11, and 3.12
- Verifies the CLI command is properly installed
- Ensures compatibility across supported Python versions

### 2. Lint (`lint.yml`)
**Trigger**: On push/PR to `master` or `main` branches

**What it does**:
- Checks code formatting with `black`
- Validates import sorting with `isort`
- Runs `flake8` for code quality checks
- Continues on error (informational only)

### 3. Publish to PyPI (`publish.yml`)
**Trigger**: When a GitHub release is published

**What it does**:
- Builds the package distribution
- Automatically publishes to PyPI using stored credentials

## Required Setup

### For PyPI Publishing

To enable automated PyPI publishing, you need to add your PyPI API token as a GitHub secret:

1. Go to your repository settings: `Settings` → `Secrets and variables` → `Actions`
2. Click `New repository secret`
3. Name: `PYPI_API_TOKEN`
4. Value: Your PyPI API token (starts with `pypi-`)
5. Click `Add secret`

### Creating a Release

To trigger automated publishing:

1. Update version in `setup.py` and `pyproject.toml`
2. Commit and push changes
3. Create a new release on GitHub:
   - Go to `Releases` → `Create a new release`
   - Create a new tag (e.g., `v0.1.2`)
   - Add release notes
   - Click `Publish release`
4. The workflow will automatically build and publish to PyPI

## Badge Status

The CI badge in the README shows the current build status. Click it to see detailed test results.
