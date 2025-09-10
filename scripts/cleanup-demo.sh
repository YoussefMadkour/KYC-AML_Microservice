#!/bin/bash

# Cleanup Demo Branches Script
# This script cleans up demo branches created during CI/CD testing

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
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

# Function to list demo branches
list_demo_branches() {
    print_info "Looking for demo branches..."
    
    # Find branches that match demo patterns
    demo_branches=$(git branch | grep -E "(demo/|test/)" | sed 's/^[* ] //' || true)
    
    if [ -z "$demo_branches" ]; then
        print_info "No demo branches found"
        return 0
    fi
    
    echo "Found demo branches:"
    echo "$demo_branches" | while read branch; do
        echo "  - $branch"
    done
    
    return 1  # Found branches
}

# Function to clean up local demo branches
cleanup_local_branches() {
    print_info "Cleaning up local demo branches..."
    
    # Get current branch
    current_branch=$(git branch --show-current)
    
    # Find demo branches
    demo_branches=$(git branch | grep -E "(demo/|test/)" | sed 's/^[* ] //' || true)
    
    if [ -z "$demo_branches" ]; then
        print_info "No local demo branches to clean up"
        return 0
    fi
    
    # Switch to main if currently on a demo branch
    if echo "$demo_branches" | grep -q "^$current_branch$"; then
        print_info "Switching from demo branch to main..."
        git checkout main 2>/dev/null || git checkout master 2>/dev/null || {
            print_error "Could not switch to main/master branch"
            return 1
        }
    fi
    
    # Delete demo branches
    echo "$demo_branches" | while read branch; do
        if [ -n "$branch" ]; then
            print_info "Deleting local branch: $branch"
            git branch -D "$branch" 2>/dev/null || {
                print_warning "Could not delete branch: $branch"
            }
        fi
    done
    
    print_success "Local demo branches cleaned up"
}

# Function to clean up remote demo branches
cleanup_remote_branches() {
    print_info "Cleaning up remote demo branches..."
    
    # Check if we have a remote
    if ! git remote | grep -q origin; then
        print_warning "No origin remote found, skipping remote cleanup"
        return 0
    fi
    
    # Fetch to get latest remote info
    git fetch origin --prune 2>/dev/null || {
        print_warning "Could not fetch from origin"
        return 0
    }
    
    # Find remote demo branches
    remote_demo_branches=$(git branch -r | grep -E "origin/(demo/|test/)" | sed 's/^[* ] origin\///' || true)
    
    if [ -z "$remote_demo_branches" ]; then
        print_info "No remote demo branches to clean up"
        return 0
    fi
    
    echo "Found remote demo branches:"
    echo "$remote_demo_branches" | while read branch; do
        echo "  - origin/$branch"
    done
    
    # Ask for confirmation
    read -p "Delete remote demo branches? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "$remote_demo_branches" | while read branch; do
            if [ -n "$branch" ]; then
                print_info "Deleting remote branch: origin/$branch"
                git push origin --delete "$branch" 2>/dev/null || {
                    print_warning "Could not delete remote branch: $branch"
                }
            fi
        done
        print_success "Remote demo branches cleaned up"
    else
        print_info "Skipping remote branch cleanup"
    fi
}

# Function to clean up demo files
cleanup_demo_files() {
    print_info "Cleaning up demo files..."
    
    # Remove demo test files
    demo_files=(
        "demo_test_file.py"
        "app/demo_test_file.py"
        "app/api/v1/test_slow.py"
    )
    
    for file in "${demo_files[@]}"; do
        if [ -f "$file" ]; then
            print_info "Removing demo file: $file"
            rm "$file"
        fi
    done
    
    # Check if there are any uncommitted demo files
    if git status --porcelain | grep -q "demo\|test_slow"; then
        print_warning "Found uncommitted demo files. You may want to commit or discard these changes."
        git status --porcelain | grep "demo\|test_slow"
    fi
    
    print_success "Demo files cleaned up"
}

# Main function
main() {
    echo "🧹 CI/CD Demo Cleanup"
    echo "===================="
    echo ""
    
    # Check if we're in a git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_error "Not in a git repository"
        exit 1
    fi
    
    # List demo branches first
    if list_demo_branches; then
        print_success "No demo branches found to clean up"
    else
        echo ""
        
        # Ask what to clean up
        echo "What would you like to clean up?"
        echo "1) Local demo branches only"
        echo "2) Remote demo branches only"
        echo "3) Both local and remote branches"
        echo "4) Demo files only"
        echo "5) Everything (branches and files)"
        echo "6) Cancel"
        
        read -p "Choose an option (1-6): " -n 1 -r
        echo ""
        echo ""
        
        case $REPLY in
            1)
                cleanup_local_branches
                ;;
            2)
                cleanup_remote_branches
                ;;
            3)
                cleanup_local_branches
                cleanup_remote_branches
                ;;
            4)
                cleanup_demo_files
                ;;
            5)
                cleanup_local_branches
                cleanup_remote_branches
                cleanup_demo_files
                ;;
            6)
                print_info "Cleanup cancelled"
                exit 0
                ;;
            *)
                print_error "Invalid option"
                exit 1
                ;;
        esac
    fi
    
    echo ""
    print_success "Cleanup completed!"
    
    # Show final status
    echo ""
    print_info "Current git status:"
    git status --short || true
    
    echo ""
    print_info "Remaining branches:"
    git branch || true
}

# Run main function
main "$@"