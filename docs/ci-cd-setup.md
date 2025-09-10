# CI/CD Pipeline Setup

This document describes the comprehensive CI/CD pipeline setup for the KYC/AML microservice using GitHub Actions.

## Overview

The CI/CD pipeline consists of multiple workflows that handle different aspects of the development lifecycle:

- **CI Pipeline** (`ci.yml`): Automated testing, code quality, and security checks
- **Deployment** (`deploy.yml`): Automated deployment to staging and production
- **Security Monitoring** (`security.yml`): Daily security scans and vulnerability monitoring
- **Performance Testing** (`performance.yml`): Load testing and performance monitoring
- **Dependency Management** (`dependabot.yml` + `dependabot-auto-merge.yml`): Automated dependency updates

## Workflows

### 1. CI Pipeline (`ci.yml`)

Triggered on every push and pull request to `main` and `develop` branches.

#### Jobs:
- **test**: Runs unit and integration tests with coverage reporting
- **code-quality**: Performs linting, formatting, and type checking
- **security-scan**: Scans for security vulnerabilities in dependencies
- **docker-build**: Builds and pushes Docker images
- **integration-test**: Tests the complete containerized application
- **quality-gate**: Ensures all quality checks pass before allowing merges

#### Services:
- PostgreSQL 15
- Redis 7
- RabbitMQ 3

#### Quality Checks:
- **Black**: Code formatting
- **isort**: Import sorting
- **flake8**: Linting
- **mypy**: Type checking
- **bandit**: Security scanning
- **safety**: Dependency vulnerability scanning

### 2. Deployment Pipeline (`deploy.yml`)

Handles deployments to staging and production environments.

#### Triggers:
- **Tags**: Automatic deployment on version tags (`v*`)
- **Manual**: Workflow dispatch for manual deployments

#### Environments:
- **Staging**: For pre-release testing (tags with `-` suffix)
- **Production**: For stable releases (clean version tags)

#### Features:
- Automated Docker image building and tagging
- Environment-specific deployments
- Smoke tests after deployment
- Automatic GitHub releases for version tags
- Rollback capability on deployment failures

### 3. Security Monitoring (`security.yml`)

Daily security monitoring and vulnerability scanning.

#### Scans:
- **Safety**: Python dependency vulnerabilities
- **Bandit**: Python code security issues
- **Semgrep**: Advanced security pattern detection
- **Trivy**: Container image vulnerabilities
- **License Check**: Ensures license compliance

#### Features:
- Automated issue creation on security findings
- SARIF upload to GitHub Security tab
- Comprehensive security reporting

### 4. Performance Testing (`performance.yml`)

Performance and load testing for the application.

#### Tests:
- **Locust**: User behavior simulation and performance testing
- **k6**: Load testing with configurable scenarios

#### Triggers:
- Pull requests to main branch
- Weekly scheduled runs
- Manual workflow dispatch

#### Metrics:
- Response time percentiles
- Error rates
- Throughput measurements
- Resource utilization

### 5. Dependency Management

Automated dependency updates using Dependabot.

#### Configuration:
- **Python packages**: Weekly updates on Mondays
- **Docker images**: Weekly updates on Tuesdays
- **GitHub Actions**: Weekly updates on Wednesdays

#### Auto-merge Rules:
- Minor and patch updates: Auto-approved and merged
- Security updates: Auto-approved and merged
- Major updates: Require manual review

## Setup Instructions

### 1. Repository Secrets

Configure the following secrets in your GitHub repository:

```bash
# Docker Hub credentials
DOCKER_USERNAME=your-dockerhub-username
DOCKER_PASSWORD=your-dockerhub-password

# GitHub token (usually auto-provided)
GITHUB_TOKEN=your-github-token
```

### 2. Environment Configuration

Set up GitHub environments for deployment:

1. Go to Settings → Environments
2. Create `staging` and `production` environments
3. Configure protection rules and required reviewers
4. Add environment-specific secrets if needed

### 3. Branch Protection Rules

Configure branch protection for `main` branch:

1. Go to Settings → Branches
2. Add rule for `main` branch
3. Enable:
   - Require pull request reviews
   - Require status checks to pass
   - Require branches to be up to date
   - Include administrators

Required status checks:
- `test`
- `code-quality`
- `security-scan`
- `quality-gate`

### 4. Code Coverage

The pipeline uses Codecov for coverage reporting. To set up:

1. Sign up at [codecov.io](https://codecov.io)
2. Connect your GitHub repository
3. Add `CODECOV_TOKEN` secret if needed (usually auto-detected)

## Usage

### Running Tests Locally

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run quality checks
black --check app/ tests/
isort --check-only app/ tests/
flake8 app/ tests/
mypy app/
bandit -r app/

# Run tests with coverage
pytest --cov=app --cov-report=html
```

### Building Docker Images

```bash
# Build API image
docker build -t kyc-aml-microservice:latest .

# Build worker image
docker build -f Dockerfile.worker -t kyc-aml-microservice:worker-latest .
```

### Manual Deployment

```bash
# Deploy to staging
gh workflow run deploy.yml -f environment=staging

# Deploy to production
gh workflow run deploy.yml -f environment=production
```

### Performance Testing

```bash
# Install Locust
pip install locust

# Run performance test
locust -f locustfile.py --headless --users 50 --spawn-rate 5 --run-time 2m --host http://localhost:8000
```

## Monitoring and Alerts

### GitHub Notifications

The pipeline will notify you of:
- Failed builds or deployments
- Security vulnerabilities found
- Performance degradation
- Dependency update failures

### Artifacts

Each workflow run produces artifacts:
- Test coverage reports
- Security scan results
- Performance test reports
- Build logs and metrics

### Quality Gates

The pipeline enforces quality gates:
- Minimum test coverage (configurable)
- No high-severity security vulnerabilities
- Code quality standards compliance
- Performance thresholds

## Troubleshooting

### Common Issues

1. **Test Failures**
   - Check test logs in the workflow run
   - Ensure all services are healthy
   - Verify environment variables

2. **Docker Build Failures**
   - Check Dockerfile syntax
   - Verify base image availability
   - Ensure all dependencies are installable

3. **Deployment Failures**
   - Check deployment logs
   - Verify environment configuration
   - Ensure target environment is accessible

4. **Security Scan Failures**
   - Review security reports
   - Update vulnerable dependencies
   - Fix identified security issues

### Getting Help

- Check workflow logs for detailed error messages
- Review the GitHub Actions documentation
- Check the repository's Issues tab for known problems
- Contact the development team for assistance

## Customization

### Adding New Checks

To add new quality checks:

1. Add the check to the appropriate job in `ci.yml`
2. Update the quality gate requirements
3. Add the check to branch protection rules

### Modifying Deployment

To customize deployment:

1. Update the deployment steps in `deploy.yml`
2. Add environment-specific configuration
3. Update smoke tests for your environment

### Performance Thresholds

To adjust performance thresholds:

1. Modify the Locust or k6 test scripts
2. Update threshold values in the workflow
3. Adjust the performance monitoring alerts

## Best Practices

1. **Keep workflows fast**: Optimize test execution and use caching
2. **Fail fast**: Run quick checks before expensive operations
3. **Parallel execution**: Run independent jobs in parallel
4. **Secure secrets**: Use GitHub secrets for sensitive data
5. **Monitor costs**: Be aware of GitHub Actions usage limits
6. **Regular updates**: Keep workflow dependencies up to date
7. **Documentation**: Keep this documentation current with changes