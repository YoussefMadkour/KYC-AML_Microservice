#!/usr/bin/env python3
"""
Script to validate CI/CD setup and configuration.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml


def check_file_exists(file_path: str) -> bool:
    """Check if a file exists."""
    return Path(file_path).exists()


def load_yaml_file(file_path: str) -> Dict[str, Any]:
    """Load and parse a YAML file."""
    try:
        with open(file_path, "r") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return {}


def validate_workflow_file(workflow_path: str, required_jobs: List[str]) -> bool:
    """Validate a GitHub Actions workflow file."""
    if not check_file_exists(workflow_path):
        print(f"❌ Missing workflow file: {workflow_path}")
        return False

    workflow = load_yaml_file(workflow_path)
    if not workflow:
        print(f"❌ Invalid YAML in: {workflow_path}")
        return False

    # Check required jobs
    jobs = workflow.get("jobs", {})
    missing_jobs = [job for job in required_jobs if job not in jobs]

    if missing_jobs:
        print(f"❌ Missing jobs in {workflow_path}: {missing_jobs}")
        return False

    print(f"✅ Valid workflow: {workflow_path}")
    return True


def validate_dependabot_config() -> bool:
    """Validate Dependabot configuration."""
    config_path = ".github/dependabot.yml"

    if not check_file_exists(config_path):
        print(f"❌ Missing Dependabot config: {config_path}")
        return False

    config = load_yaml_file(config_path)
    if not config:
        print(f"❌ Invalid Dependabot config: {config_path}")
        return False

    # Check required package ecosystems
    updates = config.get("updates", [])
    ecosystems = [update.get("package-ecosystem") for update in updates]

    required_ecosystems = ["pip", "docker", "github-actions"]
    missing_ecosystems = [eco for eco in required_ecosystems if eco not in ecosystems]

    if missing_ecosystems:
        print(
            f"❌ Missing package ecosystems in Dependabot config: {missing_ecosystems}"
        )
        return False

    print("✅ Valid Dependabot configuration")
    return True


def validate_docker_files() -> bool:
    """Validate Docker files exist."""
    docker_files = ["Dockerfile", "Dockerfile.worker", "docker-compose.yml"]

    all_valid = True
    for docker_file in docker_files:
        if not check_file_exists(docker_file):
            print(f"❌ Missing Docker file: {docker_file}")
            all_valid = False
        else:
            print(f"✅ Found Docker file: {docker_file}")

    return all_valid


def validate_requirements_files() -> bool:
    """Validate Python requirements files."""
    req_files = ["requirements.txt", "requirements-dev.txt"]

    all_valid = True
    for req_file in req_files:
        if not check_file_exists(req_file):
            print(f"❌ Missing requirements file: {req_file}")
            all_valid = False
        else:
            print(f"✅ Found requirements file: {req_file}")

    return all_valid


def validate_test_structure() -> bool:
    """Validate test directory structure."""
    test_dirs = ["tests", "tests/unit", "tests/integration", "tests/e2e"]

    all_valid = True
    for test_dir in test_dirs:
        if not Path(test_dir).is_dir():
            print(f"❌ Missing test directory: {test_dir}")
            all_valid = False
        else:
            print(f"✅ Found test directory: {test_dir}")

    return all_valid


def validate_environment_files() -> bool:
    """Validate environment configuration files."""
    env_files = [".env.example"]

    all_valid = True
    for env_file in env_files:
        if not check_file_exists(env_file):
            print(f"❌ Missing environment file: {env_file}")
            all_valid = False
        else:
            print(f"✅ Found environment file: {env_file}")

    return all_valid


def check_github_secrets_documentation() -> bool:
    """Check if GitHub secrets are documented."""
    docs_path = "docs/ci-cd-setup.md"

    if not check_file_exists(docs_path):
        print(f"❌ Missing CI/CD documentation: {docs_path}")
        return False

    with open(docs_path, "r") as f:
        content = f.read()

    required_secrets = ["DOCKER_USERNAME", "DOCKER_PASSWORD", "GITHUB_TOKEN"]
    missing_secrets = []

    for secret in required_secrets:
        if secret not in content:
            missing_secrets.append(secret)

    if missing_secrets:
        print(f"❌ Missing secret documentation: {missing_secrets}")
        return False

    print("✅ GitHub secrets are documented")
    return True


def main():
    """Main validation function."""
    print("🔍 Validating CI/CD setup...\n")

    validations = [
        # Workflow files
        (
            lambda: validate_workflow_file(
                ".github/workflows/ci.yml",
                [
                    "test",
                    "code-quality",
                    "security-scan",
                    "docker-build",
                    "quality-gate",
                ],
            ),
            "CI workflow",
        ),
        (
            lambda: validate_workflow_file(
                ".github/workflows/deploy.yml", ["deploy-staging", "deploy-production"]
            ),
            "Deployment workflow",
        ),
        (
            lambda: validate_workflow_file(
                ".github/workflows/security.yml",
                ["dependency-scan", "container-scan", "license-check"],
            ),
            "Security workflow",
        ),
        (
            lambda: validate_workflow_file(
                ".github/workflows/performance.yml", ["performance-test"]
            ),
            "Performance workflow",
        ),
        (
            lambda: validate_workflow_file(
                ".github/workflows/dependabot-auto-merge.yml", ["auto-merge"]
            ),
            "Dependabot auto-merge workflow",
        ),
        # Configuration files
        (validate_dependabot_config, "Dependabot configuration"),
        (validate_docker_files, "Docker files"),
        (validate_requirements_files, "Requirements files"),
        (validate_test_structure, "Test structure"),
        (validate_environment_files, "Environment files"),
        (check_github_secrets_documentation, "Documentation"),
    ]

    passed = 0
    total = len(validations)

    for validation_func, description in validations:
        print(f"\n📋 Validating {description}...")
        try:
            if validation_func():
                passed += 1
            else:
                print(f"❌ Validation failed for {description}")
        except Exception as e:
            print(f"❌ Error validating {description}: {e}")

    print(f"\n📊 Validation Summary:")
    print(f"✅ Passed: {passed}/{total}")
    print(f"❌ Failed: {total - passed}/{total}")

    if passed == total:
        print("\n🎉 All validations passed! CI/CD setup is complete.")
        return 0
    else:
        print(
            f"\n⚠️  {total - passed} validation(s) failed. Please fix the issues above."
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
