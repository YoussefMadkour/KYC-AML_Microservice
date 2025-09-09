# Project Structure

## Directory Organization

```
kyc-aml-microservice/
├── app/                          # Main application package
│   ├── __init__.py
│   ├── main.py                   # FastAPI application entry point
│   ├── config.py                 # Configuration and settings
│   ├── database.py               # Database connection and session management
│   ├── dependencies.py           # FastAPI dependency injection
│   │
│   ├── api/                      # API layer
│   │   ├── __init__.py
│   │   ├── deps.py               # API dependencies (auth, db sessions)
│   │   └── v1/                   # API version 1
│   │       ├── __init__.py
│   │       ├── auth.py           # Authentication endpoints
│   │       ├── users.py          # User management endpoints
│   │       ├── kyc.py            # KYC verification endpoints
│   │       └── webhooks.py       # Webhook receiver endpoints
│   │
│   ├── core/                     # Core business logic
│   │   ├── __init__.py
│   │   ├── security.py           # JWT, password hashing, encryption
│   │   ├── config.py             # Core configuration classes
│   │   └── exceptions.py         # Custom exception classes
│   │
│   ├── models/                   # SQLAlchemy models
│   │   ├── __init__.py
│   │   ├── base.py               # Base model class
│   │   ├── user.py               # User model
│   │   ├── kyc.py                # KYC check and document models
│   │   └── webhook.py            # Webhook event model
│   │
│   ├── schemas/                  # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── user.py               # User request/response schemas
│   │   ├── kyc.py                # KYC request/response schemas
│   │   ├── auth.py               # Authentication schemas
│   │   └── webhook.py            # Webhook payload schemas
│   │
│   ├── services/                 # Business logic services
│   │   ├── __init__.py
│   │   ├── user_service.py       # User management logic
│   │   ├── kyc_service.py        # KYC verification logic
│   │   ├── webhook_service.py    # Webhook processing logic
│   │   └── mock_provider.py      # Mock KYC provider simulation
│   │
│   ├── repositories/             # Data access layer
│   │   ├── __init__.py
│   │   ├── base.py               # Base repository class
│   │   ├── user_repository.py    # User data access
│   │   ├── kyc_repository.py     # KYC data access
│   │   └── webhook_repository.py # Webhook data access
│   │
│   ├── tasks/                    # Celery tasks
│   │   ├── __init__.py
│   │   ├── kyc_tasks.py          # KYC processing tasks
│   │   └── webhook_tasks.py      # Webhook processing tasks
│   │
│   └── utils/                    # Utility functions
│       ├── __init__.py
│       ├── encryption.py         # Field-level encryption utilities
│       ├── logging.py            # Structured logging setup
│       └── validators.py         # Custom validation functions
│
├── tests/                        # Test suite
│   ├── __init__.py
│   ├── conftest.py               # Pytest configuration and fixtures
│   ├── unit/                     # Unit tests
│   │   ├── test_services/
│   │   ├── test_repositories/
│   │   └── test_utils/
│   ├── integration/              # Integration tests
│   │   ├── test_api/
│   │   ├── test_database/
│   │   └── test_tasks/
│   └── e2e/                      # End-to-end tests
│       └── test_kyc_workflow.py
│
├── alembic/                      # Database migrations
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
│
├── docker/                       # Docker configuration
│   ├── Dockerfile
│   ├── Dockerfile.worker         # Celery worker container
│   └── docker-compose.yml
│
├── scripts/                      # Utility scripts
│   ├── init_db.py                # Database initialization
│   ├── create_admin.py           # Create admin user
│   └── run_tests.sh              # Test execution script
│
├── docs/                         # Documentation
│   ├── api.md                    # API documentation
│   ├── deployment.md             # Deployment guide
│   └── development.md            # Development setup
│
├── .env.example                  # Environment variables template
├── .gitignore                    # Git ignore rules
├── alembic.ini                   # Alembic configuration
├── docker-compose.yml            # Docker Compose configuration
├── pyproject.toml                # Python project configuration
├── requirements.txt              # Production dependencies
├── requirements-dev.txt          # Development dependencies
└── README.md                     # Project documentation
```

## Architectural Patterns

### Layered Architecture
- **API Layer**: FastAPI routers and endpoint definitions
- **Service Layer**: Business logic and orchestration
- **Repository Layer**: Data access abstraction
- **Model Layer**: Database entities and schemas

### Dependency Injection
- Use FastAPI's dependency injection for database sessions
- Inject services into API endpoints for testability
- Mock dependencies in tests for isolation

### Repository Pattern
- Abstract database operations behind repository interfaces
- Enable easy testing with mock repositories
- Centralize query logic and database interactions

### Service Layer Pattern
- Encapsulate business logic in service classes
- Coordinate between repositories and external services
- Handle complex workflows and business rules

## File Naming Conventions

### Python Files
- Use snake_case for all Python files and directories
- Suffix service files with `_service.py`
- Suffix repository files with `_repository.py`
- Suffix task files with `_tasks.py`

### Test Files
- Prefix all test files with `test_`
- Mirror the structure of the main application
- Group tests by functionality (unit/integration/e2e)

### Configuration Files
- Use lowercase with hyphens for Docker files
- Use standard names for configuration files (pyproject.toml, alembic.ini)
- Environment files use `.env` prefix

## Import Organization

### Import Order (enforced by isort)
1. Standard library imports
2. Third-party library imports
3. Local application imports

### Relative vs Absolute Imports
- Use absolute imports from the app package root
- Avoid relative imports except within the same module
- Import from `app.models`, `app.services`, etc.

## Code Organization Principles

### Single Responsibility
- Each module should have one clear purpose
- Services handle specific business domains
- Repositories manage single entity types

### Separation of Concerns
- Keep API logic separate from business logic
- Isolate database operations in repositories
- Separate validation logic in schemas

### Dependency Direction
- Higher layers depend on lower layers
- API → Services → Repositories → Models
- Use dependency injection to invert control