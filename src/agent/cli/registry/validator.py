import re
import tarfile
import tempfile
from pathlib import Path
from typing import Any

import yaml


class ValidationResult:
    """Result of skill package validation."""

    def __init__(self):
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.is_valid: bool = True

    def add_error(self, message: str):
        """Add an error message."""
        self.errors.append(message)
        self.is_valid = False

    def add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)

    def has_issues(self) -> bool:
        """Check if there are any errors or warnings."""
        return len(self.errors) > 0 or len(self.warnings) > 0


class SkillValidator:
    """Validates skill packages before installation."""

    def __init__(self):
        self.required_files = ["skill.yaml", "handler.py"]
        self.required_yaml_fields = ["name", "skill_id", "version", "description"]

        # Patterns that might indicate security issues
        self.dangerous_patterns = [
            r"subprocess\.call",
            r"subprocess\.run",
            r"os\.system",
            r"eval\s*\(",
            r"exec\s*\(",
            r"__import__",
            r"open\s*\([^)]*['\"]w['\"]",  # Writing files
        ]

    async def validate_package(self, package_path: Path) -> ValidationResult:
        """Validate a skill package."""
        result = ValidationResult()

        if not package_path.exists():
            result.add_error(f"Package file not found: {package_path}")
            return result

        try:
            # Extract to temporary directory for validation
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Extract package safely, preventing path traversal attacks
                try:
                    with tarfile.open(package_path, "r:gz") as tar:
                        # Validate each member before extraction to prevent path traversal
                        for member in tar.getmembers():
                            # Check for path traversal attempts
                            if member.name.startswith("/") or ".." in member.name:
                                result.add_error(f"Unsafe path in archive: {member.name}")
                                return result

                            # Check for absolute paths and normalize
                            if member.name.startswith("/"):
                                member.name = member.name.lstrip("/")

                            # Ensure we don't extract outside destination directory
                            member_path = temp_path / member.name
                            if not str(member_path.resolve()).startswith(str(temp_path.resolve())):
                                result.add_error(f"Path traversal attempt detected: {member.name}")
                                return result

                        # Extract all validated members
                        tar.extractall(temp_path)
                except Exception as e:
                    result.add_error(f"Failed to extract package: {e}")
                    return result

                # Find the extracted skill directory
                skill_dir = self._find_skill_directory(temp_path)
                if not skill_dir:
                    result.add_error("No skill directory found in package")
                    return result

                # Validate structure
                self._validate_structure(skill_dir, result)

                # Validate metadata
                self._validate_metadata(skill_dir, result)

                # Security scan
                self._security_scan(skill_dir, result)

        except Exception as e:
            result.add_error(f"Validation failed: {e}")

        return result

    def _find_skill_directory(self, temp_path: Path) -> Path:
        """Find the main skill directory in extracted package."""
        # Look for directory containing skill.yaml
        for item in temp_path.iterdir():
            if item.is_dir():
                skill_yaml = item / "skill.yaml"
                if skill_yaml.exists():
                    return item

        # Fallback: if skill.yaml is directly in temp_path
        if (temp_path / "skill.yaml").exists():
            return temp_path

        return None

    def _validate_structure(self, skill_dir: Path, result: ValidationResult):
        """Validate package file structure."""
        # Check required files
        for required_file in self.required_files:
            file_path = skill_dir / required_file
            if not file_path.exists():
                result.add_error(f"Missing required file: {required_file}")

        # Check for common optional files
        optional_files = ["README.md", "requirements.txt", "LICENSE"]
        missing_optional = []

        for optional_file in optional_files:
            if not (skill_dir / optional_file).exists():
                missing_optional.append(optional_file)

        if missing_optional:
            result.add_warning(f"Missing recommended files: {', '.join(missing_optional)}")

        # Check for tests directory
        if not (skill_dir / "tests").exists():
            result.add_warning("No tests directory found")

    def _validate_metadata(self, skill_dir: Path, result: ValidationResult):
        """Validate skill.yaml metadata."""
        skill_yaml_path = skill_dir / "skill.yaml"

        if not skill_yaml_path.exists():
            return  # Already reported in structure validation

        try:
            with open(skill_yaml_path) as f:
                skill_config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            result.add_error(f"Invalid skill.yaml format: {e}")
            return
        except Exception as e:
            result.add_error(f"Failed to read skill.yaml: {e}")
            return

        if not isinstance(skill_config, dict):
            result.add_error("skill.yaml must contain a dictionary")
            return

        # Check required fields
        for field in self.required_yaml_fields:
            if field not in skill_config:
                result.add_error(f"Missing required field in skill.yaml: {field}")
            elif not skill_config[field]:
                result.add_error(f"Empty required field in skill.yaml: {field}")

        # Validate specific fields
        if "skill_id" in skill_config:
            skill_id = skill_config["skill_id"]
            if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", skill_id):
                result.add_error(
                    "skill_id must start with letter and contain only letters, numbers, underscore, hyphen"
                )

        if "version" in skill_config:
            version = skill_config["version"]
            if not re.match(r"^\d+\.\d+\.\d+", version):
                result.add_warning("Version should follow semantic versioning (e.g., 1.0.0)")

        # Check for recommended fields
        recommended_fields = ["author", "license", "tags", "category"]
        for field in recommended_fields:
            if field not in skill_config:
                result.add_warning(f"Recommended field missing from skill.yaml: {field}")

        # Validate dependencies
        if "dependencies" in skill_config:
            self._validate_dependencies(skill_config["dependencies"], result)

    def _validate_dependencies(self, dependencies: dict[str, Any], result: ValidationResult):
        """Validate dependency specifications."""
        if not isinstance(dependencies, dict):
            result.add_error("Dependencies must be a dictionary")
            return

        # Check Python version requirement
        if "python" in dependencies:
            python_req = dependencies["python"]
            if not re.match(r">=?\d+\.\d+", python_req):
                result.add_warning("Python version requirement should be in format '>=3.10'")

        # Check packages list
        if "packages" in dependencies:
            packages = dependencies["packages"]
            if not isinstance(packages, list):
                result.add_error("Dependencies packages must be a list")
            else:
                for package in packages:
                    if not isinstance(package, str):
                        result.add_error("Package dependencies must be strings")
                    elif not re.match(r"^[a-zA-Z0-9_-]+", package):
                        result.add_warning(f"Unusual package name: {package}")

    def _security_scan(self, skill_dir: Path, result: ValidationResult):
        """Perform basic security scanning."""
        handler_path = skill_dir / "handler.py"

        if not handler_path.exists():
            return  # Already reported in structure validation

        try:
            with open(handler_path, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            result.add_warning(f"Could not read handler.py for security scan: {e}")
            return

        # Check for dangerous patterns
        for pattern in self.dangerous_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                result.add_warning(f"Potentially dangerous pattern found: {pattern}")

        # Check imports
        import_lines = [line.strip() for line in content.split("\n") if line.strip().startswith(("import ", "from "))]

        dangerous_imports = ["subprocess", "os", "sys", "pickle", "marshal"]
        for line in import_lines:
            for dangerous in dangerous_imports:
                if dangerous in line:
                    result.add_warning(f"Potentially dangerous import: {line}")

        # Check for network operations
        network_patterns = [
            r"requests\.",
            r"urllib\.",
            r"http\.",
            r"socket\.",
            r"ftplib\.",
        ]

        for pattern in network_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                result.add_warning("Code contains network operations - ensure proper error handling")
                break

    def validate_installed_skill(self, skill_dir: Path) -> ValidationResult:
        """Validate an already installed skill."""
        result = ValidationResult()

        if not skill_dir.exists():
            result.add_error(f"Skill directory not found: {skill_dir}")
            return result

        self._validate_structure(skill_dir, result)
        self._validate_metadata(skill_dir, result)

        return result
