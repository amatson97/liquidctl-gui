# Release Automation Scripts

This directory contains helper scripts for managing releases.

## Quick Start

### For a new release:

```bash
# Interactive wizard (recommended for first-time use)
./scripts/prepare-release.sh

# Or directly specify version
./scripts/release.sh 0.3.0
```

## Scripts

### `pre-release-check.sh` (Recommended First Step)
Validates everything is ready for release:
- ✓ Checks for uncommitted changes
- ✓ Checks for unpushed commits
- ✓ Lists open PRs (requires GitHub CLI)
- ✓ Runs test suite
- ✓ Verifies CHANGELOG is updated
- ✓ Checks version consistency

**Usage:**
```bash
./scripts/pre-release-check.sh
```

### `prepare-release.sh` (Interactive)
Interactive wizard that guides you through:
- Choosing version bump type (patch/minor/major)
- Pre-release checklist
- Automatically runs `release.sh`

**Usage:**
```bash
./scripts/prepare-release.sh
```

### `release.sh` (Automated)
Automates the release process:
1. ✓ Validates version format
2. ✓ Checks for uncommitted changes
3. ✓ Updates `__version__` in `__init__.py`
4. ✓ Runs tests
5. ✓ Creates git commit
6. ✓ Creates annotated git tag
7. ✓ Optionally pushes to GitHub

**Usage:**
```bash
./scripts/release.sh 0.3.0
```

**What it does:**
- Updates version in `src/liquidctl_gui/__init__.py`
- Runs test suite to verify nothing is broken
- Creates commit: `chore: bump version to X.Y.Z`
- Creates git tag: `vX.Y.Z`
- Prompts to push to GitHub

### Other Scripts

#### `generate_udev_rules.py`
Generates udev rules for detected liquidctl devices.

#### `install_udev_rules.sh`
Installs udev rules and configures permissions.

#### `fix-hwmon-permissions.sh`
Fixes hwmon node permissions for current session.

## GitHub Actions

### Automatic Release Creation
When you push a tag (e.g., `v0.3.0`), GitHub Actions automatically:
- Runs tests
- Creates a GitHub Release
- Attaches CHANGELOG.md content

See: [.github/workflows/release.yml](../.github/workflows/release.yml)

## Release Workflow

### Working with Pull Requests

1. **Contributors submit PRs** from their forks
   - They follow [CONTRIBUTING.md](../CONTRIBUTING.md)
   - Fill out the PR template
   - Tests run automatically (if CI is configured)

2. **Review and merge PRs**
   - Review code on GitHub
   - Use "Squash and merge" for clean history
   - Merge to `main` branch

3. **Update CHANGELOG** with merged changes
   ```markdown
   ## [Unreleased]
   ### Added
   - New feature from PR #123 (@contributor)
   ### Fixed
   - Bug fix from PR #124 (@contributor)
   ```

4. **Prepare for release**
   ```bash
   git checkout main
   git pull origin main
   ./scripts/pre-release-check.sh  # Verify everything is ready
   ```

5. **Create release**
   ```bash
   ./scripts/prepare-release.sh
   ```

### Standard Release Workflow (Without PRs)

1. **Update CHANGELOG.md**
   ```markdown
   ## [0.3.0] - 2026-02-XX
   ### Added
   - New feature description
   ```

2. **Run prepare script**
   ```bash
   ./scripts/prepare-release.sh
   ```

3. **Review and push**
   ```bash
   git log -1  # Review the commit
   git push origin main
   git push origin v0.3.0
   ```

4. **Create GitHub Release** (automated via GitHub Actions)
   - Or manually: https://github.com/amatson97/liquidctl-gui/releases

## Version Numbering

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0): Breaking changes
- **MINOR** (0.X.0): New features, backward compatible
- **PATCH** (0.0.X): Bug fixes

## Tips

- Always update CHANGELOG.md before releasing
- Run tests manually before committing: `PYTHONPATH=src python -m unittest tests.test_unit`
- Test the app: `./launch.sh`
- Use descriptive commit messages
- Tag messages are shown in GitHub releases
