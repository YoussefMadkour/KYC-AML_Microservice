#!/bin/bash

# CI/CD Pipeline Demo Script
# This script demonstrates the CI/CD pipeline functionality

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_step() {
    echo -e "${BLUE}🔄 $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    print_step "Checking prerequisites..."
    
    # Check if we're in a git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_error "Not in a git repository"
        exit 1
    fi
    
    # Check if GitHub CLI is installed
    if ! command -v gh &> /dev/null; then
        print_warning "GitHub CLI (gh) not found. Some features will be limited."
        GH_AVAILABLE=false
    else
        GH_AVAILABLE=true
    fi
    
    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not found"
        exit 1
    fi
    
    # Check if Docker is available
    if ! command -v docker &> /dev/null; then
        print_warning "Docker not found. Some tests will be skipped."
        DOCKER_AVAILABLE=false
    else
        DOCKER_AVAILABLE=true
    fi
    
    print_success "Prerequisites check completed"
}

# Validate CI/CD setup
validate_setup() {
    print_step "Validating CI/CD setup..."
    
    if [ -f "scripts/validate-ci-setup.py" ]; then
        python3 scripts/validate-ci-setup.py
        if [ $? -eq 0 ]; then
            print_success "CI/CD setup validation passed"
        else
            print_error "CI/CD setup validation failed"
            exit 1
        fi
    else
        print_error "Validation script not found"
        exit 1
    fi
}

# Test local code quality checks
test_code_quality() {
    print_step "Testing code quality checks locally..."
    
    # Install development dependencies if not already installed
    if [ ! -d "venv" ]; then
        print_info "Creating virtual environment..."
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements-dev.txt
    else
        source venv/bin/activate
    fi
    
    # Run Black (code formatting check)
    print_info "Running Black formatting check..."
    if black --check --diff app/ tests/ 2>/dev/null; then
        print_success "Black formatting check passed"
    else
        print_warning "Black formatting issues found (this is expected in demo)"
    fi
    
    # Run isort (import sorting check)
    print_info "Running isort import sorting check..."
    if isort --check-only --diff app/ tests/ 2>/dev/null; then
        print_success "isort check passed"
    else
        print_warning "isort issues found (this is expected in demo)"
    fi
    
    # Run flake8 (linting)
    print_info "Running flake8 linting..."
    if flake8 app/ tests/ --max-line-length=88 --extend-ignore=E203,W503 2>/dev/null; then
        print_success "flake8 linting passed"
    else
        print_warning "flake8 issues found (this is expected in demo)"
    fi
    
    # Run mypy (type checking)
    print_info "Running mypy type checking..."
    if mypy app/ --ignore-missing-imports 2>/dev/null; then
        print_success "mypy type checking passed"
    else
        print_warning "mypy issues found (this is expected in demo)"
    fi
    
    deactivate
}

# Test security scanning
test_security_scanning() {
    print_step "Testing security scanning..."
    
    source venv/bin/activate
    
    # Install security tools
    pip install -q bandit safety
    
    # Run bandit security scan
    print_info "Running bandit security scan..."
    if bandit -r app/ --severity-level medium 2>/dev/null; then
        print_success "Bandit security scan passed"
    else
        print_warning "Bandit found potential security issues"
    fi
    
    # Run safety dependency check
    print_info "Running safety dependency check..."
    if safety check 2>/dev/null; then
        print_success "Safety dependency check passed"
    else
        print_warning "Safety found vulnerable dependencies"
    fi
    
    deactivate
}

# Test Docker builds
test_docker_builds() {
    if [ "$DOCKER_AVAILABLE" = true ]; then
        print_step "Testing Docker builds..."
        
        # Build API image
        print_info "Building API Docker image..."
        if docker build -t kyc-aml-microservice:test . > /dev/null 2>&1; then
            print_success "API Docker image built successfully"
        else
            print_error "Failed to build API Docker image"
        fi
        
        # Build Worker image
        print_info "Building Worker Docker image..."
        if docker build -f Dockerfile.worker -t kyc-aml-microservice:worker-test . > /dev/null 2>&1; then
            print_success "Worker Docker image built successfully"
        else
            print_error "Failed to build Worker Docker image"
        fi
        
        # Clean up test images
        docker rmi kyc-aml-microservice:test kyc-aml-microservice:worker-test > /dev/null 2>&1 || true
    else
        print_warning "Skipping Docker tests (Docker not available)"
    fi
}

# Simulate CI workflow
simulate_ci_workflow() {
    print_step "Simulating CI workflow..."
    
    print_info "This simulates what happens when you push code to GitHub:"
    echo "  1. Code quality checks (Black, isort, flake8, mypy)"
    echo "  2. Security scanning (bandit, safety)"
    echo "  3. Unit and integration tests"
    echo "  4. Docker image building"
    echo "  5. Quality gate validation"
    
    # Run a subset of tests if available
    if [ -d "tests" ]; then
        source venv/bin/activate
        print_info "Running unit tests..."
        if python -m pytest tests/unit/ -v --tb=short 2>/dev/null; then
            print_success "Unit tests passed"
        else
            print_warning "Some unit tests failed (expected in demo environment)"
        fi
        deactivate
    fi
    
    print_success "CI workflow simulation completed"
}

# Show GitHub Actions status (if available)
show_github_status() {
    if [ "$GH_AVAILABLE" = true ]; then
        print_step "Checking GitHub Actions status..."
        
        # Check if we're authenticated with GitHub
        if gh auth status > /dev/null 2>&1; then
            print_info "Recent workflow runs:"
            gh run list --limit 5 2>/dev/null || print_warning "No workflow runs found or repository not connected"
            
            print_info "Available workflows:"
            ls .github/workflows/*.yml | while read workflow; do
                echo "  - $(basename "$workflow")"
            done
        else
            print_warning "Not authenticated with GitHub CLI. Run 'gh auth login' to connect."
        fi
    fi
}

# Create demo branch and test
create_demo_test() {
    print_step "Creating demo test scenario..."
    
    # Save current branch
    CURRENT_BRANCH=$(git branch --show-current)
    
    # Create demo branch
    DEMO_BRANCH="demo/ci-pipeline-test-$(date +%s)"
    git checkout -b "$DEMO_BRANCH" > /dev/null 2>&1
    
    # Create a test file with intentional issues
    cat > demo_test_file.py << 'EOF'
# Demo file to test CI pipeline
import   os,sys
def badly_formatted_function(  ):
    return"This will fail formatting checks"

# This function has a potential security issue
def unsafe_function():
    exec("print('This is unsafe')")  # bandit will flag this
    
class   DemoClass:
    def __init__(self):
        pass
EOF
    
    git add demo_test_file.py
    git commit -m "demo: add test file with formatting and security issues" > /dev/null 2>&1
    
    print_info "Created demo branch: $DEMO_BRANCH"
    print_info "Added test file with intentional issues:"
    echo "  - Poor formatting (will fail Black)"
    echo "  - Security issue (will fail Bandit)"
    echo "  - Import sorting issues (will fail isort)"
    
    if [ "$GH_AVAILABLE" = true ] && gh auth status > /dev/null 2>&1; then
        print_info "Push this branch to GitHub to see CI pipeline in action:"
        echo "  git push origin $DEMO_BRANCH"
        echo "  gh pr create --title 'Demo: Test CI Pipeline' --body 'Testing CI/CD pipeline'"
    fi
    
    # Return to original branch
    git checkout "$CURRENT_BRANCH" > /dev/null 2>&1
    
    print_warning "Demo branch created but not pushed. Clean up with:"
    echo "  git branch -D $DEMO_BRANCH"
}

# Show workflow file contents
show_workflow_examples() {
    print_step "Showing workflow examples..."
    
    print_info "CI Workflow (.github/workflows/ci.yml):"
    echo "  - Runs on: push, pull_request to main/develop"
    echo "  - Jobs: test, code-quality, security-scan, docker-build, quality-gate"
    echo "  - Services: PostgreSQL, Redis, RabbitMQ"
    
    print_info "Deploy Workflow (.github/workflows/deploy.yml):"
    echo "  - Runs on: version tags (v*), manual trigger"
    echo "  - Environments: staging, production"
    echo "  - Features: automated deployment, rollback capability"
    
    print_info "Security Workflow (.github/workflows/security.yml):"
    echo "  - Runs on: daily schedule, manual trigger"
    echo "  - Scans: dependencies, code, containers, licenses"
    echo "  - Creates issues for security findings"
    
    print_info "Performance Workflow (.github/workflows/performance.yml):"
    echo "  - Runs on: PR to main, weekly schedule"
    echo "  - Tools: Locust, k6"
    echo "  - Monitors: response times, error rates, throughput"
}

# Main execution
main() {
    echo "🚀 CI/CD Pipeline Demo"
    echo "====================="
    echo ""
    
    check_prerequisites
    echo ""
    
    validate_setup
    echo ""
    
    test_code_quality
    echo ""
    
    test_security_scanning
    echo ""
    
    test_docker_builds
    echo ""
    
    simulate_ci_workflow
    echo ""
    
    show_github_status
    echo ""
    
    show_workflow_examples
    echo ""
    
    # Ask if user wants to create demo test
    read -p "Create a demo test branch? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        create_demo_test
        echo ""
    fi
    
    print_success "Demo completed!"
    echo ""
    echo "Next steps:"
    echo "1. Push your code to GitHub to see the CI pipeline in action"
    echo "2. Create a pull request to test the full workflow"
    echo "3. Set up repository secrets for Docker Hub integration"
    echo "4. Configure branch protection rules"
    echo ""
    echo "For detailed usage examples, see: docs/ci-cd-usage-examples.md"
}

# Run main function
main "$@"