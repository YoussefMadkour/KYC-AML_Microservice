
# Remaining Manual Fixes Needed

## 1. Type Annotation Issues
- Add proper return type annotations to functions
- Fix async/await usage in repositories
- Add proper type hints for complex types

## 2. Pydantic V2 Migration
- Replace @validator with @field_validator
- Update Pydantic configuration to use ConfigDict
- Fix deprecated Pydantic patterns

## 3. SQLAlchemy Issues
- Fix Column type assignments
- Ensure proper async/await usage
- Update deprecated SQLAlchemy patterns

## 4. Test Issues
- Some tests expect methods that don't exist
- Mock configurations need updating
- Test data setup may need fixes

## Quick Commands to Run:
```bash
# Fix remaining formatting
black app/ tests/ scripts/
isort app/ tests/ scripts/

# Check for remaining issues
flake8 app/ tests/ --max-line-length=88 --extend-ignore=E203,W503,F401,F841
mypy app/ --ignore-missing-imports

# Run tests to see what's left
pytest tests/unit/ -x -v
```
