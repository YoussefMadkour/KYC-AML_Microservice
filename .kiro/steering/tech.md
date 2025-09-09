# Technology Stack

## Core Framework
- **FastAPI**: Modern Python web framework with automatic OpenAPI documentation
- **Python 3.12+**: Primary programming language Already installed on my macbook python3
- **Pydantic**: Data validation and settings management
- **SQLAlchemy**: ORM for database operations with async support

## Database & Storage
- **PostgreSQL**: Primary database for persistent data storage
- **Redis**: Caching layer and Celery result backend
- **Alembic**: Database migration management

## Asynchronous Processing
- **Celery**: Distributed task queue for background processing
- **RabbitMQ**: Message broker for task queuing
- **Asyncio**: Async/await patterns for concurrent operations

## Security & Authentication
- **JWT (PyJWT)**: Token-based authentication
- **Cryptography**: Field-level encryption for PII data
- **Passlib**: Password hashing with bcrypt
- **HMAC**: Webhook signature verification

## Development & Testing
- **pytest**: Testing framework with async support
- **pytest-asyncio**: Async test support
- **httpx**: HTTP client for testing API endpoints
- **testcontainers**: Integration testing with real services
- **Black**: Code formatting
- **isort**: Import sorting
- **mypy**: Static type checking

## Containerization & Deployment
- **Docker**: Application containerization
- **Docker Compose**: Local development orchestration
- **Multi-stage builds**: Optimized production images

## Monitoring & Observability
- **Prometheus**: Metrics collection
- **Structured logging**: JSON-formatted logs with correlation IDs
- **Health checks**: Application and dependency monitoring

## Common Commands

### Development Setup
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Database setup
alembic upgrade head

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test categories
pytest tests/unit/
pytest tests/integration/
pytest -m "not slow"  # Skip slow tests
```

### Code Quality
```bash
# Format code
black app/ tests/
isort app/ tests/

# Type checking
mypy app/

# Linting
flake8 app/ tests/
```

### Docker Operations
```bash
# Build and start all services
docker-compose up --build

# Start in background
docker-compose up -d

# View logs
docker-compose logs -f api

# Run tests in container
docker-compose exec api pytest

# Database migrations in container
docker-compose exec api alembic upgrade head
```

### Celery Workers
```bash
# Start Celery worker (development)
celery -A app.worker worker --loglevel=info

# Start Celery worker with Docker
docker-compose exec worker celery -A app.worker worker --loglevel=info

# Monitor tasks
celery -A app.worker flower
```

## Environment Configuration
- Use `.env` files for local development
- Environment-specific settings via Pydantic Settings
- Secrets management through environment variables
- Database URLs and connection strings configurable per environment