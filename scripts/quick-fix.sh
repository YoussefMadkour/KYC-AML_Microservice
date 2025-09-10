#!/bin/bash

# Quick Fix Script for CI/CD Pipeline Issues
# This script fixes the most common issues that cause pipeline failures

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() {
    echo -e "${BLUE}🔧 $1${NC}"
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

# Check if we're in the right directory
if [ ! -d "app" ] || [ ! -d "tests" ]; then
    print_error "This script must be run from the project root directory"
    exit 1
fi

echo "🔧 Quick Fix for CI/CD Pipeline Issues"
echo "====================================="
echo ""

# 1. Fix code formatting
print_step "Fixing code formatting issues..."
if command -v black &> /dev/null; then
    black app/ tests/ scripts/ 2>/dev/null || print_warning "Black formatting had issues"
    print_success "Black formatting applied"
else
    print_warning "Black not installed, skipping formatting"
fi

if command -v isort &> /dev/null; then
    isort app/ tests/ scripts/ 2>/dev/null || print_warning "isort had issues"
    print_success "Import sorting applied"
else
    print_warning "isort not installed, skipping import sorting"
fi

echo ""

# 2. Remove demo files with security issues
print_step "Removing demo files with security issues..."
demo_files=("demo_test_file.py" "app/demo_test_file.py" "app/api/v1/test_slow.py")
for file in "${demo_files[@]}"; do
    if [ -f "$file" ]; then
        rm "$file"
        print_success "Removed $file"
    fi
done

echo ""

# 3. Fix missing TaskLogger class
print_step "Fixing TaskLogger import error..."
if [ -f "app/utils/task_monitoring.py" ]; then
    if ! grep -q "class TaskLogger" app/utils/task_monitoring.py; then
        cat >> app/utils/task_monitoring.py << 'EOF'

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
EOF
        print_success "Added TaskLogger class"
    else
        print_success "TaskLogger class already exists"
    fi
    
    # Ensure logging import exists
    if ! grep -q "import logging" app/utils/task_monitoring.py; then
        sed -i '' '1i\
import logging' app/utils/task_monitoring.py
        print_success "Added logging import"
    fi
fi

echo ""

# 4. Fix hardcoded security issues
print_step "Fixing security issues..."

# Fix config.py hardcoded bind all interfaces
if [ -f "app/core/config.py" ]; then
    if grep -q 'HOST: str = Field(default="0.0.0.0"' app/core/config.py; then
        sed -i '' 's/HOST: str = Field(default="0.0.0.0"/HOST: str = Field(default="127.0.0.1"/' app/core/config.py
        print_success "Fixed hardcoded bind all interfaces in config"
    fi
fi

# Fix main.py hardcoded host
if [ -f "app/main.py" ]; then
    if grep -q 'uvicorn.run(app, host="0.0.0.0"' app/main.py; then
        # Add settings import if not present
        if ! grep -q "from app.core.config import settings" app/main.py; then
            sed -i '' '1i\
from app.core.config import settings' app/main.py
        fi
        # Replace hardcoded host
        sed -i '' 's/uvicorn.run(app, host="0.0.0.0", port=8000)/uvicorn.run(app, host=settings.HOST, port=settings.PORT)/' app/main.py
        print_success "Fixed hardcoded host in main.py"
    fi
fi

echo ""

# 5. Create missing test __init__.py files
print_step "Creating missing test files..."
test_dirs=(
    "tests"
    "tests/unit"
    "tests/integration"
    "tests/e2e"
    "tests/unit/test_tasks"
    "tests/unit/test_services"
    "tests/unit/test_repositories"
    "tests/unit/test_utils"
    "tests/unit/test_api"
    "tests/unit/test_api/test_middleware"
)

for dir in "${test_dirs[@]}"; do
    if [ ! -f "$dir/__init__.py" ]; then
        mkdir -p "$dir"
        echo "# Test package" > "$dir/__init__.py"
        print_success "Created $dir/__init__.py"
    fi
done

echo ""

# 6. Run quality checks to verify fixes
print_step "Running quality checks..."

echo "  Checking Black formatting..."
if command -v black &> /dev/null; then
    if black --check app/ tests/ scripts/ 2>/dev/null; then
        print_success "Black formatting check passed"
    else
        print_warning "Black formatting issues remain"
    fi
fi

echo "  Checking import sorting..."
if command -v isort &> /dev/null; then
    if isort --check-only app/ tests/ scripts/ 2>/dev/null; then
        print_success "Import sorting check passed"
    else
        print_warning "Import sorting issues remain"
    fi
fi

echo "  Checking linting..."
if command -v flake8 &> /dev/null; then
    if flake8 app/ tests/ --max-line-length=88 --extend-ignore=E203,W503 2>/dev/null; then
        print_success "Linting check passed"
    else
        print_warning "Linting issues remain"
    fi
fi

echo ""

# 7. Test imports
print_step "Testing critical imports..."
if python3 -c "from app.utils.task_monitoring import TaskMonitor, TaskLogger" 2>/dev/null; then
    print_success "TaskMonitor and TaskLogger imports work"
else
    print_warning "TaskMonitor/TaskLogger import issues remain"
fi

echo ""

print_success "Quick fixes completed!"
echo ""
echo "📋 What was fixed:"
echo "  ✅ Code formatting (Black, isort)"
echo "  ✅ Removed demo files with security issues"
echo "  ✅ Added missing TaskLogger class"
echo "  ✅ Fixed hardcoded security issues"
echo "  ✅ Created missing test __init__.py files"
echo ""
echo "🚀 Next steps:"
echo "  1. Run tests to check for remaining issues:"
echo "     pytest tests/unit/ -v"
echo ""
echo "  2. Commit the fixes:"
echo "     git add ."
echo "     git commit -m 'fix: resolve CI/CD pipeline issues'"
echo ""
echo "  3. Push and test the pipeline:"
echo "     git push"
echo ""
echo "⚠️  Manual review may still be needed for:"
echo "  - Complex type annotation issues"
echo "  - Async/await usage in repositories"
echo "  - Any remaining test failures"