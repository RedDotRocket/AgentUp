#!/usr/bin/env python3
"""Release automation script for AgentUp.

This script automates the version management and release process:
1. Updates version in pyproject.toml
2. Syncs version across all configuration files
3. Updates templates and other files
4. Runs tests and quality checks
5. Creates git tag and prepares for release

Usage:
    python scripts/release.py --version 0.6.0 --dry-run
    python scripts/release.py --version 0.6.0 --confirm
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

import structlog

# Add src to Python path for imports
script_dir = Path(__file__).parent
project_root = script_dir.parent
src_dir = project_root / "src"
sys.path.insert(0, str(src_dir))

from agent.utils.config_sync import find_and_sync_all_configs, sync_config_version
from agent.utils.version import get_version

logger = structlog.get_logger(__name__)


class ReleaseManager:
    """Manages the release process for AgentUp."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.pyproject_path = project_root / "pyproject.toml"
    
    def get_current_version(self) -> str:
        """Get the current version from pyproject.toml."""
        try:
            content = self.pyproject_path.read_text(encoding='utf-8')
            match = re.search(r'^version = ["\']([^"\']+)["\']', content, re.MULTILINE)
            if match:
                return match.group(1)
            raise ValueError("Version not found in pyproject.toml")
        except Exception as e:
            logger.error("Failed to get current version", error=str(e))
            raise
    
    def update_pyproject_version(self, new_version: str) -> bool:
        """Update version in pyproject.toml."""
        try:
            content = self.pyproject_path.read_text(encoding='utf-8')
            old_content = content
            
            # Update version line
            version_pattern = r'^(version = )["\']([^"\']+)["\']'
            new_content = re.sub(
                version_pattern, 
                f'\\1"{new_version}"', 
                content, 
                flags=re.MULTILINE
            )
            
            if new_content == old_content:
                logger.warning("No version found to update in pyproject.toml")
                return False
            
            self.pyproject_path.write_text(new_content, encoding='utf-8')
            logger.info("Updated pyproject.toml", old_version=re.search(r'^version = ["\']([^"\']+)["\']', old_content, re.MULTILINE).group(1), new_version=new_version)
            return True
            
        except Exception as e:
            logger.error("Failed to update pyproject.toml", error=str(e))
            return False
    
    def sync_all_configs(self, version: str) -> dict[str, bool]:
        """Sync version across all configuration files."""
        logger.info("Syncing configuration files", version=version)
        
        results = find_and_sync_all_configs(self.project_root, version)
        
        # Log results
        updated_files = [path for path, updated in results.items() if updated]
        unchanged_files = [path for path, updated in results.items() if not updated]
        
        if updated_files:
            logger.info("Updated configuration files", files=updated_files)
        if unchanged_files:
            logger.debug("Configuration files already up to date", files=unchanged_files)
        
        return results
    
    def run_quality_checks(self) -> bool:
        """Run linting, formatting, and type checking."""
        logger.info("Running quality checks")
        
        checks = [
            ["uv", "run", "ruff", "check", "--fix", "src/", "tests/"],
            ["uv", "run", "ruff", "format", "src/", "tests/"],
            ["uv", "run", "mypy", "src/"],
            ["uv", "run", "bandit", "-r", "src/", "-ll"]
        ]
        
        for check in checks:
            try:
                result = subprocess.run(check, capture_output=True, text=True, cwd=self.project_root)
                if result.returncode != 0:
                    logger.error("Quality check failed", 
                                command=" ".join(check), 
                                stdout=result.stdout, 
                                stderr=result.stderr)
                    return False
                logger.debug("Quality check passed", command=" ".join(check))
            except Exception as e:
                logger.error("Failed to run quality check", command=" ".join(check), error=str(e))
                return False
        
        logger.info("All quality checks passed")
        return True
    
    def run_tests(self) -> bool:
        """Run the test suite."""
        logger.info("Running test suite")
        
        try:
            result = subprocess.run([
                "uv", "run", "pytest", 
                "tests/test_*.py", "tests/test_core/", "tests/test_cli/",
                "-v", "-m", "not integration and not e2e and not performance"
            ], capture_output=True, text=True, cwd=self.project_root)
            
            if result.returncode != 0:
                logger.error("Tests failed", stdout=result.stdout, stderr=result.stderr)
                return False
            
            logger.info("All tests passed")
            return True
            
        except Exception as e:
            logger.error("Failed to run tests", error=str(e))
            return False
    
    def create_git_tag(self, version: str, dry_run: bool = False) -> bool:
        """Create a git tag for the release."""
        tag_name = f"v{version}"
        
        if dry_run:
            logger.info("Would create git tag", tag=tag_name)
            return True
        
        try:
            # Check if tag already exists
            result = subprocess.run(
                ["git", "tag", "-l", tag_name], 
                capture_output=True, text=True, cwd=self.project_root
            )
            
            if result.stdout.strip():
                logger.error("Git tag already exists", tag=tag_name)
                return False
            
            # Create the tag
            result = subprocess.run([
                "git", "tag", "-a", tag_name, 
                "-m", f"Release version {version}"
            ], capture_output=True, text=True, cwd=self.project_root)
            
            if result.returncode != 0:
                logger.error("Failed to create git tag", 
                           tag=tag_name, stderr=result.stderr)
                return False
            
            logger.info("Created git tag", tag=tag_name)
            return True
            
        except Exception as e:
            logger.error("Failed to create git tag", tag=tag_name, error=str(e))
            return False
    
    def check_git_status(self) -> bool:
        """Check if git working directory is clean."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"], 
                capture_output=True, text=True, cwd=self.project_root
            )
            
            if result.stdout.strip():
                logger.warning("Git working directory is not clean")
                logger.info("Uncommitted changes:\n" + result.stdout)
                return False
            
            return True
            
        except Exception as e:
            logger.error("Failed to check git status", error=str(e))
            return False
    
    def prepare_release(self, new_version: str, dry_run: bool = False, 
                       skip_tests: bool = False, skip_quality: bool = False) -> bool:
        """Prepare a release with the specified version."""
        logger.info("Starting release preparation", 
                   version=new_version, dry_run=dry_run)
        
        current_version = self.get_current_version()
        logger.info("Current version", version=current_version)
        
        if current_version == new_version:
            logger.warning("New version is same as current version")
            return False
        
        # Validate version format
        if not re.match(r'^\d+\.\d+\.\d+$', new_version):
            logger.error("Invalid version format (must be x.y.z)", version=new_version)
            return False
        
        if not dry_run:
            # Check git status
            if not self.check_git_status():
                logger.error("Please commit or stash changes before release")
                return False
        
        # Step 1: Update pyproject.toml
        if not dry_run:
            if not self.update_pyproject_version(new_version):
                return False
        else:
            logger.info("Would update pyproject.toml", 
                       old_version=current_version, new_version=new_version)
        
        # Step 2: Sync all config files
        if not dry_run:
            results = self.sync_all_configs(new_version)
            if not any(results.values()):
                logger.info("No configuration files needed updates")
        else:
            logger.info("Would sync configuration files", version=new_version)
        
        # Step 3: Run quality checks
        if not skip_quality:
            if not dry_run:
                if not self.run_quality_checks():
                    return False
            else:
                logger.info("Would run quality checks")
        
        # Step 4: Run tests
        if not skip_tests:
            if not dry_run:
                if not self.run_tests():
                    return False
            else:
                logger.info("Would run tests")
        
        # Step 5: Create git tag
        if not self.create_git_tag(new_version, dry_run):
            return False
        
        logger.info("Release preparation completed successfully", version=new_version)
        
        if not dry_run:
            logger.info("Next steps:")
            logger.info("1. Review changes: git diff HEAD~1")
            logger.info("2. Push tag: git push origin v" + new_version)
            logger.info("3. Create GitHub release")
            logger.info("4. Build and publish: python -m build && python -m twine upload dist/*")
        
        return True


def main():
    """Main entry point for the release script."""
    parser = argparse.ArgumentParser(description="AgentUp release automation")
    parser.add_argument("--version", required=True, help="New version (e.g., 0.6.0)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--confirm", action="store_true", help="Actually perform the release")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")
    parser.add_argument("--skip-quality", action="store_true", help="Skip quality checks")
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.confirm:
        print("ERROR: Must specify either --dry-run or --confirm")
        sys.exit(1)
    
    # Configure logging
    import logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer()
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Find project root
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent
    
    # Create release manager and run
    release_manager = ReleaseManager(project_root)
    
    try:
        success = release_manager.prepare_release(
            args.version, 
            dry_run=args.dry_run,
            skip_tests=args.skip_tests,
            skip_quality=args.skip_quality
        )
        
        if success:
            print(f"\n✅ Release preparation {'simulated' if args.dry_run else 'completed'} successfully!")
            sys.exit(0)
        else:
            print(f"\n❌ Release preparation failed!")
            sys.exit(1)
    
    except Exception as e:
        logger.error("Release preparation failed with exception", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()