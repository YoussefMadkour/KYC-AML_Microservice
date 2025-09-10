# KYC/AML Microservice

A production-ready FastAPI microservice that simulates real-world fintech KYC (Know Your Customer) and AML (Anti-Money Laundering) verification workflows. The system demonstrates enterprise-grade microservice architecture patterns without requiring paid third-party services.

## Features

- 🚀 **FastAPI** with automatic OpenAPI documentation
- 🔐 **JWT Authentication** with role-based access control
- 🗄️ **PostgreSQL** database with SQLAlchemy ORM
- 🔄 **Asynchronous Processing** with Celery and RabbitMQ
- 🔒 **Field-level Encryption** for sensitive PII data
- 🪝 **Webhook Handling** with signature verification
- 📊 **Structured Logging** with correlation IDs
- 🐳 **Docker Containerization** for consistent deployment
- 🧪 **Comprehensive Testing** with pytest and testcontainers
- 🔄 **CI/CD Pipeline** with GitHub Actions
- 🛡️ **Security Monitoring** with automated vulnerability scanning
- 📈 **Performance Testing** with load testing and monitoring

## Quick Start

### Prerequisites

- Python 3.12+
- Docker and Docker Compose
- PostgreSQL (or use Docker)
- Redis (or use Docker)
- RabbitMQ (or use Docker)

### Development Setup

1. **Clone and setup virtual environment:**
   ```bash
   git clone <repository-url>
   cd kyc-aml-microservice
   python3 -m venv venv
   source venv/bin/activate  # On macOS/Linux
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements-dev.txt
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Start services with Docker:**
   ```bash
   docker-compose up -d postgres redis rabbitmq
   ```

5. **Run database migrations:**
   ```bash
   alembic upgrade head
   ```

6. **Start the development server:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

7. **Access the API documentation:**
   - Swagger UI: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

### Docker Development

Run the entire stack with Docker Compose:

```bash
docker-compose up --build
```

## Project Structure

```
kyc-aml-microservice/
├── app/                          # Main application package
│   ├── api/                      # API layer (FastAPI routers)
│   ├── core/                     # Core business logic
│   ├── models/                   # SQLAlchemy models
│   ├── schemas/                  # Pydantic schemas
│   ├── services/                 # Business logic services
│   ├── repositories/             # Data access layer
│   ├── tasks/                    # Celery tasks
│   └── utils/                    # Utility functions
├── tests/                        # Test suite
├── alembic/                      # Database migrations
├── docker/                       # Docker configuration
└── docs/                         # Documentation
```

## API Endpoints

### Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - User authentication
- `POST /auth/refresh` - Token refresh

### KYC Management
- `POST /kyc/checks` - Initiate KYC verification
- `GET /kyc/checks/{check_id}` - Get KYC status
- `GET /kyc/checks` - List KYC checks

### Webhooks
- `POST /webhooks/kyc/{provider}` - Receive KYC webhooks

### Health & Monitoring
- `GET /health` - Health check
- `GET /metrics` - Prometheus metrics

## Testing

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

## Development Commands

```bash
# Format code
black app/ tests/
isort app/ tests/

# Type checking
mypy app/

# Linting
flake8 app/ tests/

# Start Celery worker
celery -A app.worker worker --loglevel=info

# Database migrations
alembic revision --autogenerate -m "Description"
alembic upgrade head

# Validate CI/CD setup
./scripts/validate-ci.sh
```

## Configuration

The application uses Pydantic Settings for configuration management. All settings can be configured via environment variables. See `.env.example` for available options.

Key configuration areas:
- Database connection
- Redis and Celery settings
- JWT and encryption keys
- Mock provider configuration
- Logging and monitoring

## Security Features

- JWT-based authentication with refresh tokens
- Role-based access control (RBAC)
- Field-level encryption for PII data
- Webhook signature verification
- Rate limiting and request validation
- Comprehensive audit logging
- Automated security scanning in CI/CD pipeline
- Dependency vulnerability monitoring
- Container security scanning

## CI/CD Pipeline

The project includes a comprehensive CI/CD pipeline with GitHub Actions:

- **Automated Testing**: Unit, integration, and end-to-end tests
- **Code Quality**: Linting, formatting, and type checking
- **Security Scanning**: Dependency and code vulnerability scanning
- **Performance Testing**: Load testing and performance monitoring
- **Automated Deployment**: Staging and production deployments
- **Dependency Management**: Automated dependency updates with Dependabot

See [docs/ci-cd-setup.md](docs/ci-cd-setup.md) for detailed setup instructions.

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## Support

For questions and support, please open an issue in the GitHub repository.