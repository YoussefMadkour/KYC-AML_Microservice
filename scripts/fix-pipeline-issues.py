#!/usr/bin/env python3
"""
Fix Pipeline Issues Script
This script automatically fixes common CI/CD pipeline issues including:
- Code formatting issues
- Import sorting problems
- Type annotation issues
- Security vulnerabilities
- Test import errors
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


def run_command(cmd: str, cwd: str = None) -> tuple[int, str, str]:
    """Run a shell command and return exit code, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd.split(), cwd=cwd, capture_output=True, text=True, timeout=300
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)


def print_step(message: str):
    """Print a step message."""
    print(f"🔧 {message}")


def print_success(message: str):
    """Print a success message."""
    print(f"✅ {message}")


def print_warning(message: str):
    """Print a warning message."""
    print(f"⚠️  {message}")


def print_error(message: str):
    """Print an error message."""
    print(f"❌ {message}")


def fix_code_formatting():
    """Fix code formatting issues with Black and isort."""
    print_step("Fixing code formatting issues...")

    # Run Black to fix formatting
    print("  Running Black formatter...")
    exit_code, stdout, stderr = run_command("black app/ tests/ scripts/")
    if exit_code == 0:
        print_success("Black formatting applied")
    else:
        print_warning(f"Black formatting issues: {stderr}")

    # Run isort to fix import sorting
    print("  Running isort...")
    exit_code, stdout, stderr = run_command("isort app/ tests/ scripts/")
    if exit_code == 0:
        print_success("Import sorting applied")
    else:
        print_warning(f"isort issues: {stderr}")


def fix_missing_task_logger():
    """Fix the missing TaskLogger import error."""
    print_step("Fixing TaskLogger import error...")

    # Check if TaskLogger exists in task_monitoring.py
    task_monitoring_path = Path("app/utils/task_monitoring.py")
    if not task_monitoring_path.exists():
        print_error("task_monitoring.py not found")
        return

    with open(task_monitoring_path, "r") as f:
        content = f.read()

    # Add TaskLogger class if it doesn't exist
    if "class TaskLogger" not in content:
        task_logger_code = '''

class TaskLogger:
    """Logger for Celery tasks with structured logging."""
    
    def __init__(self, task_name: str, task_id: str = None):
        self.task_name = task_name
        self.task_id = task_id or "unknown"
        self.logger = logging.getLogger(f"task.{task_name}")
    
    def info(self, message: str, **kwargs):
        """Log info message with task context."""
        self.logger.info(
            message,
            extra={
                "task_name": self.task_name,
                "task_id": self.task_id,
                **kwargs
            }
        )
    
    def error(self, message: str, **kwargs):
        """Log error message with task context."""
        self.logger.error(
            message,
            extra={
                "task_name": self.task_name,
                "task_id": self.task_id,
                **kwargs
            }
        )
    
    def warning(self, message: str, **kwargs):
        """Log warning message with task context."""
        self.logger.warning(
            message,
            extra={
                "task_name": self.task_name,
                "task_id": self.task_id,
                **kwargs
            }
        )
'''

        # Add import for logging at the top
        if "import logging" not in content:
            content = "import logging\n" + content

        # Add TaskLogger class at the end
        content += task_logger_code

        with open(task_monitoring_path, "w") as f:
            f.write(content)

        print_success("Added TaskLogger class to task_monitoring.py")
    else:
        print_success("TaskLogger class already exists")


def fix_type_annotations():
    """Fix common type annotation issues."""
    print_step("Fixing type annotation issues...")

    # Common fixes for type annotations
    fixes = [
        # Fix Dict imports
        ("from typing import Dict", "from typing import Dict, List, Optional, Any"),
        # Fix missing return type annotations
        ("def ", "def "),  # This would need more sophisticated parsing
    ]

    # Files that commonly need type fixes
    files_to_fix = [
        "app/services/mock_provider.py",
        "app/schemas/user.py",
        "app/schemas/kyc.py",
        "app/repositories/user_repository.py",
        "app/api/v1/webhooks.py",
        "app/api/v1/users.py",
        "app/api/v1/kyc.py",
        "app/api/v1/auth.py",
    ]

    for file_path in files_to_fix:
        if Path(file_path).exists():
            try:
                with open(file_path, "r") as f:
                    content = f.read()

                # Add missing typing imports
                if "from typing import" not in content and (
                    "Dict" in content or "List" in content
                ):
                    # Add typing import after other imports
                    lines = content.split("\n")
                    import_index = 0
                    for i, line in enumerate(lines):
                        if line.startswith("from ") or line.startswith("import "):
                            import_index = i + 1

                    lines.insert(
                        import_index,
                        "from typing import Dict, List, Optional, Any, Union",
                    )
                    content = "\n".join(lines)

                # Fix common type annotation patterns
                content = re.sub(
                    r"def ([^(]+)\([^)]*\):", r"def \1(...) -> Any:", content
                )

                with open(file_path, "w") as f:
                    f.write(content)

                print(f"  Fixed type annotations in {file_path}")
            except Exception as e:
                print_warning(f"Could not fix {file_path}: {e}")

    print_success("Type annotation fixes applied")


def fix_security_issues():
    """Fix common security issues found by bandit."""
    print_step("Fixing security issues...")

    # Remove demo file with security issues if it exists
    demo_files = ["demo_test_file.py", "app/demo_test_file.py"]
    for demo_file in demo_files:
        if Path(demo_file).exists():
            os.remove(demo_file)
            print_success(f"Removed demo file with security issues: {demo_file}")

    # Fix hardcoded bind all interfaces in config
    config_path = Path("app/core/config.py")
    if config_path.exists():
        with open(config_path, "r") as f:
            content = f.read()

        # Replace hardcoded 0.0.0.0 with environment variable
        content = content.replace(
            'HOST: str = Field(default="0.0.0.0"',
            'HOST: str = Field(default="127.0.0.1"',
        )

        with open(config_path, "w") as f:
            f.write(content)

        print_success("Fixed hardcoded bind all interfaces in config")

    # Fix main.py hardcoded host
    main_path = Path("app/main.py")
    if main_path.exists():
        with open(main_path, "r") as f:
            content = f.read()

        # Replace hardcoded 0.0.0.0 with config
        content = content.replace(
            'uvicorn.run(app, host="0.0.0.0", port=8000)',
            "uvicorn.run(app, host=settings.HOST, port=settings.PORT)",
        )

        # Add settings import if not present
        if "from app.core.config import settings" not in content:
            content = "from app.core.config import settings\n" + content

        with open(main_path, "w") as f:
            f.write(content)

        print_success("Fixed hardcoded host in main.py")


def fix_pydantic_validators():
    """Fix deprecated Pydantic validators."""
    print_step("Fixing deprecated Pydantic validators...")

    # Files with Pydantic schemas
    schema_files = [
        "app/schemas/user.py",
        "app/schemas/auth.py",
        "app/schemas/kyc.py",
        "app/schemas/webhook.py",
    ]

    for file_path in schema_files:
        if Path(file_path).exists():
            try:
                with open(file_path, "r") as f:
                    content = f.read()

                # Replace @validator with @field_validator
                content = re.sub(
                    r'@validator\("([^"]+)"\)', r'@field_validator("\1")', content
                )

                # Add field_validator import
                if "@field_validator" in content and "field_validator" not in content:
                    content = content.replace(
                        "from pydantic import", "from pydantic import field_validator,"
                    )

                with open(file_path, "w") as f:
                    f.write(content)

                print(f"  Fixed Pydantic validators in {file_path}")
            except Exception as e:
                print_warning(f"Could not fix {file_path}: {e}")

    print_success("Pydantic validator fixes applied")


def fix_async_await_issues():
    """Fix missing await statements."""
    print_step("Fixing async/await issues...")

    # This is a complex fix that would require AST parsing
    # For now, we'll just add a note about manual fixes needed
    print_warning("Async/await issues require manual review:")
    print("  - Check repository method calls for missing 'await'")
    print("  - Ensure async functions are properly awaited")
    print("  - Review coroutine usage in services")


def create_missing_test_files():
    """Create missing test files to fix import errors."""
    print_step("Creating missing test files...")

    # Create missing __init__.py files
    test_dirs = [
        "tests",
        "tests/unit",
        "tests/integration",
        "tests/e2e",
        "tests/unit/test_tasks",
        "tests/unit/test_services",
        "tests/unit/test_repositories",
        "tests/unit/test_utils",
        "tests/unit/test_api",
    ]

    for test_dir in test_dirs:
        init_file = Path(test_dir) / "__init__.py"
        if not init_file.exists():
            init_file.parent.mkdir(parents=True, exist_ok=True)
            init_file.write_text("# Test package\n")
            print(f"  Created {init_file}")

    print_success("Missing test files created")


def run_quality_checks():
    """Run quality checks to verify fixes."""
    print_step("Running quality checks to verify fixes...")

    checks = [
        ("black --check app/ tests/", "Black formatting"),
        ("isort --check-only app/ tests/", "Import sorting"),
        (
            "flake8 app/ tests/ --max-line-length=88 --extend-ignore=E203,W503",
            "Linting",
        ),
    ]

    all_passed = True
    for cmd, name in checks:
        print(f"  Running {name}...")
        exit_code, stdout, stderr = run_command(cmd)
        if exit_code == 0:
            print_success(f"{name} passed")
        else:
            print_warning(f"{name} issues remain")
            all_passed = False

    return all_passed


def main():
    """Main function to fix all pipeline issues."""
    print("🔧 Fixing CI/CD Pipeline Issues")
    print("===============================")
    print()

    # Check if we're in the right directory
    if not Path("app").exists() or not Path("tests").exists():
        print_error("This script must be run from the project root directory")
        sys.exit(1)

    # Install required packages
    print_step("Installing required packages...")
    run_command("pip install black isort flake8 mypy bandit")

    # Apply fixes
    fix_code_formatting()
    print()

    fix_missing_task_logger()
    print()

    fix_security_issues()
    print()

    fix_pydantic_validators()
    print()

    create_missing_test_files()
    print()

    fix_async_await_issues()
    print()

    # Run quality checks
    print_step("Verifying fixes...")
    if run_quality_checks():
        print()
        print_success("All automated fixes applied successfully!")
        print()
        print("📋 Manual fixes still needed:")
        print("  1. Review async/await usage in repositories and services")
        print("  2. Add proper type annotations to functions missing them")
        print("  3. Fix any remaining mypy type errors")
        print("  4. Review and test the application functionality")
        print()
        print("🚀 Next steps:")
        print("  1. Run tests: pytest tests/unit/")
        print(
            "  2. Commit changes: git add . && git commit -m 'fix: resolve CI/CD pipeline issues'"
        )
        print("  3. Push and test pipeline: git push")
    else:
        print()
        print_warning("Some issues remain. Please review the output above.")
        print("You may need to run the individual tools manually:")
        print("  black app/ tests/")
        print("  isort app/ tests/")
        print("  flake8 app/ tests/")


if __name__ == "__main__":
    main()
