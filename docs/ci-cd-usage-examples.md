# CI/CD Pipeline Usage Examples

This guide provides practical examples of how to use and test the CI/CD pipeline for the KYC/AML microservice.

## 🚀 Getting Started

### 1. Initial Setup and Validation

First, validate that your CI/CD setup is complete:

```bash
# Run the validation script
./scripts/validate-ci.sh

# Or run the Python validator directly
python3 scripts/validate-ci-setup.py
```

**Expected Output:**
```
🔍 Validating CI/CD Pipeline Setup
==================================
📦 Installing validation dependencies...
🚀 Running validation checks...

✅ Valid workflow: .github/workflows/ci.yml
✅ Valid workflow: .github/workflows/deploy.yml
✅ Valid workflow: .github/workflows/security.yml
✅ Valid workflow: .github/workflows/performance.yml
✅ Valid workflow: .github/workflows/dependabot-auto-merge.yml
✅ Valid Dependabot configuration
✅ Found Docker file: Dockerfile
✅ Found Docker file: Dockerfile.worker
✅ Found Docker file: docker-compose.yml

🎉 All validations passed! CI/CD setup is complete.
```

### 2. Repository Setup

Set up your GitHub repository with the necessary configurations:

```bash
# 1. Push your code to GitHub
git add .
git commit -m "feat: add comprehensive CI/CD pipeline"
git push origin main

# 2. Set up repository secrets (via GitHub UI or CLI)
gh secret set DOCKER_USERNAME --body "your-dockerhub-username"
gh secret set DOCKER_PASSWORD --body "your-dockerhub-password"

# 3. Configure branch protection rules
gh api repos/:owner/:repo/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["test","code-quality","security-scan","quality-gate"]}' \
  --field enforce_admins=true \
  --field required_pull_request_reviews='{"required_approving_review_count":1}' \
  --field restrictions=null
```

## 🧪 Testing the CI Pipeline

### Example 1: Triggering CI on Pull Request

Create a simple change to test the CI pipeline:

```bash
# 1. Create a feature branch
git checkout -b feature/test-ci-pipeline

# 2. Make a small change (e.g., update a comment)
echo "# Test CI pipeline" >> app/main.py

# 3. Commit and push
git add app/main.py
git commit -m "test: trigger CI pipeline"
git push origin feature/test-ci-pipeline

# 4. Create a pull request
gh pr create --title "Test CI Pipeline" --body "Testing the CI/CD pipeline functionality"
```

**What happens:**
- CI workflow triggers automatically
- Runs tests, code quality checks, security scans
- Builds Docker images
- Reports results on the PR

### Example 2: Simulating Test Failures

Test how the pipeline handles failures:

```bash
# 1. Create a branch with intentional issues
git checkout -b feature/test-failures

# 2. Add code that will fail linting
cat >> app/test_file.py << 'EOF'
# This will fail Black formatting
def   badly_formatted_function(  ):
    return"no spaces"
EOF

# 3. Commit and push
git add app/test_file.py
git commit -m "test: add poorly formatted code"
git push origin feature/test-failures

# 4. Create PR and observe failures
gh pr create --title "Test Pipeline Failures" --body "Testing how pipeline handles code quality issues"
```

**Expected Result:**
- Code quality job fails due to Black formatting issues
- Quality gate prevents merge
- PR shows failed status checks

### Example 3: Testing Security Scanning

Add a dependency with known vulnerabilities:

```bash
# 1. Create security test branch
git checkout -b feature/test-security-scan

# 2. Add a vulnerable dependency to requirements.txt
echo "django==2.0.1  # Known vulnerabilities" >> requirements.txt

# 3. Commit and push
git add requirements.txt
git commit -m "test: add vulnerable dependency"
git push origin feature/test-security-scan
```

**Expected Result:**
- Security scan job detects vulnerabilities
- Safety check fails
- Pipeline prevents merge

## 🚢 Testing Deployment Workflows

### Example 1: Staging Deployment

Test staging deployment with a pre-release tag:

```bash
# 1. Create a pre-release version
git checkout main
git pull origin main

# 2. Create and push a pre-release tag
git tag v1.0.0-beta.1
git push origin v1.0.0-beta.1
```

**What happens:**
- Deploy workflow triggers automatically
- Builds production Docker images
- Deploys to staging environment
- Runs smoke tests

### Example 2: Production Deployment

Test production deployment with a stable release:

```bash
# 1. Create a stable release tag
git tag v1.0.0
git push origin v1.0.0
```

**What happens:**
- Deploy workflow triggers for production
- Creates GitHub release
- Deploys to production environment
- Runs production smoke tests

### Example 3: Manual Deployment

Trigger manual deployment using GitHub CLI:

```bash
# Deploy to staging manually
gh workflow run deploy.yml -f environment=staging

# Deploy to production manually (requires approval)
gh workflow run deploy.yml -f environment=production
```

## 🔒 Testing Security Monitoring

### Example 1: Daily Security Scan

The security workflow runs daily, but you can trigger it manually:

```bash
# Trigger security scan manually
gh workflow run security.yml
```

**What it does:**
- Scans dependencies for vulnerabilities
- Checks code for security issues
- Scans Docker images for vulnerabilities
- Creates GitHub issues if problems found

### Example 2: Viewing Security Reports

Access security scan results:

```bash
# List recent workflow runs
gh run list --workflow=security.yml

# Download security reports from a specific run
gh run download <run-id> --name security-reports
```

## 📊 Testing Performance Monitoring

### Example 1: Performance Test on PR

Performance tests run automatically on PRs to main:

```bash
# 1. Create a performance-impacting change
git checkout -b feature/test-performance

# 2. Add a slow endpoint (for testing)
cat >> app/api/v1/test.py << 'EOF'
import time
from fastapi import APIRouter

router = APIRouter()

@router.get("/slow")
def slow_endpoint():
    time.sleep(2)  # Simulate slow operation
    return {"message": "This is slow"}
EOF

# 3. Commit and create PR
git add app/api/v1/test.py
git commit -m "test: add slow endpoint for performance testing"
git push origin feature/test-performance
gh pr create --title "Test Performance Impact" --body "Testing performance monitoring"
```

### Example 2: Manual Load Testing

Trigger load testing manually:

```bash
# Run performance tests
gh workflow run performance.yml
```

**What it does:**
- Starts the application with Docker Compose
- Runs Locust performance tests
- Generates performance reports
- Checks against performance thresholds

## 🔄 Testing Dependency Management

### Example 1: Dependabot Updates

Dependabot automatically creates PRs for dependency updates. Test the auto-merge:

```bash
# 1. Wait for Dependabot to create a PR (or create one manually for testing)
# 2. The auto-merge workflow will:
#    - Wait for CI to pass
#    - Auto-approve minor/patch updates
#    - Auto-merge if all checks pass
#    - Require manual review for major updates
```

### Example 2: Manual Dependency Update

Test dependency updates manually:

```bash
# 1. Update a dependency
pip install --upgrade fastapi
pip freeze | grep fastapi >> requirements.txt

# 2. Commit and push
git add requirements.txt
git commit -m "deps: update fastapi to latest version"
git push origin main
```

## 🔍 Monitoring and Debugging

### Viewing Workflow Status

```bash
# List all workflow runs
gh run list

# View specific workflow runs
gh run list --workflow=ci.yml
gh run list --workflow=deploy.yml

# View logs for a specific run
gh run view <run-id> --log
```

### Downloading Artifacts

```bash
# List artifacts for a run
gh run view <run-id>

# Download specific artifacts
gh run download <run-id> --name test-results
gh run download <run-id> --name security-reports
gh run download <run-id> --name performance-report
```

### Debugging Failed Workflows

```bash
# View failed run details
gh run view <failed-run-id> --log

# Re-run failed jobs
gh run rerun <run-id>

# Re-run only failed jobs
gh run rerun <run-id> --failed
```

## 📈 Real-World Usage Scenarios

### Scenario 1: Feature Development Workflow

```bash
# 1. Developer creates feature branch
git checkout -b feature/new-kyc-provider

# 2. Implements feature with tests
# ... code changes ...

# 3. Commits follow conventional commits
git commit -m "feat(kyc): add new KYC provider integration"

# 4. Pushes and creates PR
git push origin feature/new-kyc-provider
gh pr create --title "Add New KYC Provider" --body "Implements integration with XYZ provider"

# 5. CI runs automatically:
#    - Tests pass ✅
#    - Code quality checks pass ✅
#    - Security scans pass ✅
#    - Performance tests pass ✅

# 6. Code review and merge
gh pr merge --squash
```

### Scenario 2: Hotfix Deployment

```bash
# 1. Create hotfix branch from main
git checkout main
git pull origin main
git checkout -b hotfix/security-patch

# 2. Apply critical fix
# ... fix security issue ...

# 3. Fast-track through CI
git commit -m "fix(security): patch critical vulnerability"
git push origin hotfix/security-patch

# 4. Create PR with priority label
gh pr create --title "URGENT: Security Patch" --body "Critical security fix" --label priority

# 5. After approval, create hotfix release
git checkout main
git merge hotfix/security-patch
git tag v1.0.1
git push origin v1.0.1  # Triggers production deployment
```

### Scenario 3: Monitoring Security Issues

```bash
# 1. Daily security scan finds vulnerability
# 2. Automated issue is created in GitHub
# 3. Developer investigates:

# View the security issue
gh issue list --label security

# Download security reports
gh run list --workflow=security.yml
gh run download <latest-run-id> --name security-reports

# 4. Fix the vulnerability
pip install --upgrade vulnerable-package
git commit -m "fix(deps): update vulnerable dependency"
git push origin main
```

## 🎯 Best Practices for Using the Pipeline

### 1. Commit Message Conventions

Use conventional commits for better automation:

```bash
# Features
git commit -m "feat(api): add new KYC endpoint"

# Bug fixes
git commit -m "fix(auth): resolve JWT token expiration issue"

# Dependencies
git commit -m "deps: update fastapi to v0.104.0"

# CI/CD changes
git commit -m "ci: add performance testing workflow"

# Documentation
git commit -m "docs: update API documentation"
```

### 2. Branch Naming Conventions

```bash
# Features
git checkout -b feature/user-authentication
git checkout -b feature/kyc-provider-integration

# Bug fixes
git checkout -b fix/database-connection-leak
git checkout -b fix/webhook-signature-validation

# Hotfixes
git checkout -b hotfix/security-vulnerability
git checkout -b hotfix/critical-bug

# Chores
git checkout -b chore/update-dependencies
git checkout -b chore/cleanup-tests
```

### 3. Testing Strategy

```bash
# Run tests locally before pushing
pytest tests/unit/                    # Fast unit tests
pytest tests/integration/             # Integration tests
pytest tests/e2e/                     # End-to-end tests

# Run code quality checks
black --check app/ tests/
isort --check-only app/ tests/
flake8 app/ tests/
mypy app/

# Run security checks
bandit -r app/
safety check
```

### 4. Performance Monitoring

```bash
# Local performance testing
pip install locust
locust -f tests/performance/locustfile.py --headless --users 10 --spawn-rate 2 --run-time 1m --host http://localhost:8000

# Monitor application metrics
curl http://localhost:8000/metrics  # Prometheus metrics
curl http://localhost:8000/health   # Health check
```

This comprehensive guide shows you exactly how to use and test every aspect of the CI/CD pipeline. Each example includes the commands to run and the expected outcomes, making it easy to verify that everything is working correctly.