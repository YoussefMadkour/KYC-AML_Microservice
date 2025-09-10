# CI/CD Pipeline Test Example

This is a step-by-step example showing how to test the CI/CD pipeline in practice.

## 🚀 Quick Test Example

### Step 1: Run the Demo Script

```bash
# Run the comprehensive demo
./scripts/demo-ci-pipeline.sh
```

**What this does:**
- ✅ Validates your CI/CD setup
- ✅ Tests code quality checks locally
- ✅ Tests security scanning
- ✅ Tests Docker builds
- ✅ Simulates the CI workflow
- ✅ Creates a demo branch with intentional issues

### Step 2: Test with GitHub (Real Pipeline)

If you have a GitHub repository set up:

```bash
# 1. Push the demo branch to trigger CI
git push origin demo/ci-pipeline-test-1757523132

# 2. Create a pull request to see the full pipeline
gh pr create --title "Test CI Pipeline" --body "Testing CI/CD pipeline with intentional issues"

# 3. Watch the workflow run
gh run list --workflow=ci.yml
gh run watch  # Watch the latest run in real-time
```

**Expected Results:**
- ❌ Code quality checks will fail (Black, isort formatting issues)
- ❌ Security scan will fail (Bandit detects unsafe `exec()`)
- ❌ Quality gate will prevent merge
- 📊 You'll see detailed reports in GitHub Actions

### Step 3: Fix Issues and Test Success

```bash
# 1. Switch to the demo branch
git checkout demo/ci-pipeline-test-1757523132

# 2. Fix the formatting issues
black demo_test_file.py
isort demo_test_file.py

# 3. Fix the security issue
# Edit demo_test_file.py and remove the unsafe exec() line
sed -i '' '/exec(/d' demo_test_file.py

# 4. Commit the fixes
git add demo_test_file.py
git commit -m "fix: resolve formatting and security issues"

# 5. Push the fixes
git push origin demo/ci-pipeline-test-1757523132
```

**Expected Results:**
- ✅ All code quality checks pass
- ✅ Security scans pass
- ✅ Quality gate allows merge
- 🎉 PR can be merged

## 📊 Real-World Example Output

Here's what you'll see when the pipeline runs:

### ✅ Successful CI Run
```
✅ test (2m 34s)
  - Unit tests: 374 passed
  - Integration tests: 45 passed
  - Coverage: 87%

✅ code-quality (1m 12s)
  - Black: ✅ Code formatted correctly
  - isort: ✅ Imports sorted correctly
  - flake8: ✅ No linting issues
  - mypy: ✅ Type checking passed
  - bandit: ✅ No security issues

✅ security-scan (45s)
  - safety: ✅ No vulnerable dependencies
  - Container scan: ✅ No vulnerabilities

✅ docker-build (3m 21s)
  - API image: ✅ Built successfully
  - Worker image: ✅ Built successfully
  - Images pushed to registry

✅ quality-gate (5s)
  - All checks passed ✅
```

### ❌ Failed CI Run (with issues)
```
❌ code-quality (1m 8s)
  - Black: ❌ Code formatting issues found
    app/demo_test_file.py would be reformatted
  - isort: ❌ Import sorting issues
    app/demo_test_file.py imports are incorrectly sorted
  - bandit: ❌ Security issues found
    B102: exec_used - Use of exec detected

❌ quality-gate (3s)
  - Code quality checks failed ❌
  - Cannot proceed with merge
```

## 🔧 Testing Different Scenarios

### Scenario 1: Test Performance Impact

```bash
# Create a branch with performance issues
git checkout -b test/performance-impact

# Add a slow endpoint
cat >> app/api/v1/test_slow.py << 'EOF'
from fastapi import APIRouter
import time

router = APIRouter()

@router.get("/slow-endpoint")
def slow_endpoint():
    time.sleep(3)  # Simulate slow operation
    return {"message": "This is intentionally slow"}
EOF

# Commit and push
git add app/api/v1/test_slow.py
git commit -m "test: add slow endpoint for performance testing"
git push origin test/performance-impact

# Create PR and watch performance tests
gh pr create --title "Test Performance Impact" --body "Testing performance monitoring"
```

### Scenario 2: Test Security Vulnerability

```bash
# Create a branch with security issues
git checkout -b test/security-vulnerability

# Add vulnerable dependency
echo "requests==2.20.0  # Has known CVE" >> requirements.txt

# Commit and push
git add requirements.txt
git commit -m "test: add vulnerable dependency"
git push origin test/security-vulnerability

# Watch security scan fail
gh pr create --title "Test Security Scan" --body "Testing security vulnerability detection"
```

### Scenario 3: Test Deployment

```bash
# Test staging deployment
git checkout main
git tag v1.0.0-beta.1
git push origin v1.0.0-beta.1

# Watch deployment workflow
gh run list --workflow=deploy.yml
gh run watch

# Test production deployment
git tag v1.0.0
git push origin v1.0.0
```

## 📈 Monitoring and Debugging

### View Workflow Logs

```bash
# List recent runs
gh run list

# View specific run
gh run view <run-id> --log

# Download artifacts
gh run download <run-id>
```

### Check Coverage Reports

```bash
# After a successful run, download coverage
gh run download <run-id> --name coverage-report

# View HTML coverage report
open coverage-report/htmlcov/index.html
```

### Security Reports

```bash
# Download security scan results
gh run download <run-id> --name security-reports

# View bandit report
cat security-reports/bandit-report.json | jq '.'

# View safety report
cat security-reports/safety-report.json | jq '.'
```

## 🎯 Key Takeaways

1. **The demo script shows you everything locally** - Run `./scripts/demo-ci-pipeline.sh` to see how all components work
2. **GitHub Actions provides the real pipeline** - Push code to see the actual CI/CD in action
3. **Quality gates prevent bad code** - The pipeline blocks merges when issues are found
4. **Comprehensive reporting** - Every aspect is monitored and reported
5. **Easy debugging** - Logs and artifacts help you understand and fix issues

## 🔄 Next Steps

1. **Set up your GitHub repository** with the workflows
2. **Configure secrets** for Docker Hub integration
3. **Set up branch protection** rules
4. **Test with real changes** to see the pipeline in action
5. **Customize thresholds** and rules for your needs

The CI/CD pipeline is now ready to use! Every push and pull request will automatically trigger the comprehensive testing and quality checks.