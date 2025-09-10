#!/bin/bash

# Validate CI/CD Setup Script
# This script validates the GitHub Actions CI/CD pipeline configuration

set -e

echo "🔍 Validating CI/CD Pipeline Setup"
echo "=================================="

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: This script must be run from the project root directory"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is required but not installed"
    exit 1
fi

# Install required Python packages for validation
echo "📦 Installing validation dependencies..."
pip install -q pyyaml

# Run the Python validation script
echo "🚀 Running validation checks..."
python3 scripts/validate-ci-setup.py

# Additional shell-based checks
echo ""
echo "🔧 Running additional checks..."

# Check if .github directory exists
if [ ! -d ".github" ]; then
    echo "❌ Missing .github directory"
    exit 1
else
    echo "✅ Found .github directory"
fi

# Check if workflows directory exists
if [ ! -d ".github/workflows" ]; then
    echo "❌ Missing .github/workflows directory"
    exit 1
else
    echo "✅ Found .github/workflows directory"
fi

# Count workflow files
workflow_count=$(find .github/workflows -name "*.yml" -o -name "*.yaml" | wc -l)
echo "📄 Found $workflow_count workflow files"

if [ $workflow_count -lt 5 ]; then
    echo "⚠️  Warning: Expected at least 5 workflow files"
fi

# Check for common CI/CD files
files_to_check=(
    ".github/dependabot.yml"
    "docs/ci-cd-setup.md"
    "Dockerfile"
    "Dockerfile.worker"
    "docker-compose.yml"
    "requirements.txt"
    "requirements-dev.txt"
    ".env.example"
)

missing_files=()
for file in "${files_to_check[@]}"; do
    if [ ! -f "$file" ]; then
        missing_files+=("$file")
    fi
done

if [ ${#missing_files[@]} -eq 0 ]; then
    echo "✅ All required files are present"
else
    echo "❌ Missing files:"
    for file in "${missing_files[@]}"; do
        echo "   - $file"
    done
fi

echo ""
echo "🎯 Validation complete!"
echo ""
echo "Next steps:"
echo "1. Review any failed validations above"
echo "2. Set up GitHub repository secrets (see docs/ci-cd-setup.md)"
echo "3. Configure branch protection rules"
echo "4. Test the pipeline by creating a pull request"