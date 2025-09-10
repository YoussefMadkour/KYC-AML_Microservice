# Docker Deployment Guide

This guide covers the containerized deployment of the KYC/AML microservice using Docker and Docker Compose.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- At least 4GB RAM available for containers
- Ports 5432, 5672, 6379, 8000, 15672 available

## Quick Start

1. **Clone and navigate to the project:**
   ```bash
   git clone <repository-url>
   cd kyc-aml-microservice
   ```

2. **Start all services:**
   ```bash
   docker-compose up -d
   ```

3. **Verify deployment:**
   ```bash
   ./scripts/test-docker-deployment.sh
   ```

4. **Access the services:**
   - API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - RabbitMQ Management: http://localhost:15672 (guest/guest)

## Architecture

The Docker deployment includes the following services:

### Core Services
- **API**: FastAPI application server
- **Worker**: Celery worker for background tasks
- **PostgreSQL**: Primary database
- **Redis**: Caching and Celery result backend
- **RabbitMQ**: Message broker for task queuing

### Optional Services
- **Flower**: Celery monitoring (requires additional setup)

## Configuration Files

### Docker Compose Files
- `docker-compose.yml`: Development environment
- `docker-compose.prod.yml`: Production environment
- `docker-compose.tasks.yml`: Tasks-only environment

### Dockerfiles
- `Dockerfile`: Multi-stage build for API service
- `Dockerfile.worker`: Celery worker container

### Environment Files
- `.env.example`: Template for local development
- `.env.docker`: Docker-specific configuration

## Service Configuration

### API Service
```yaml
api:
  build: .
  ports:
    - "8000:8000"
  environment:
    - DATABASE_URL=postgresql://kyc_user:kyc_password@postgres:5432/kyc_db
    - REDIS_URL=redis://redis:6379/0
    - CELERY_BROKER_URL=amqp://guest:guest@rabbitmq:5672//
  depends_on:
    - postgres
    - redis
    - rabbitmq
```

### Resource Limits
- **API**: 1GB RAM, 1 CPU
- **Worker**: 1GB RAM, 1 CPU
- **PostgreSQL**: 512MB RAM, 0.5 CPU
- **Redis**: 256MB RAM, 0.25 CPU
- **RabbitMQ**: 512MB RAM, 0.5 CPU

## Health Checks

All services include health checks:
- **API**: HTTP health endpoint
- **Worker**: Celery ping command
- **PostgreSQL**: pg_isready command
- **Redis**: Redis ping command
- **RabbitMQ**: rabbitmq-diagnostics ping

## Deployment Commands

### Development Deployment
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Production Deployment
```bash
# Use production configuration
docker-compose -f docker-compose.prod.yml up -d

# Scale workers
docker-compose -f docker-compose.prod.yml up -d --scale worker=3
```

### Build and Deploy Script
```bash
# Build images and deploy
./scripts/docker-build.sh --type production
./scripts/docker-deploy.sh --prod --detach
```

## Environment Variables

### Required Variables
```bash
# Database
DATABASE_URL=postgresql://user:password@host:port/database

# Redis
REDIS_URL=redis://host:port/db

# Celery
CELERY_BROKER_URL=amqp://user:password@host:port//
CELERY_RESULT_BACKEND=redis://host:port/db

# Security
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret
ENCRYPTION_KEY=your-encryption-key
WEBHOOK_SECRET_KEY=your-webhook-secret
```

### Optional Variables
```bash
# Application
ENVIRONMENT=development
DEBUG=false
LOG_LEVEL=INFO

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
```

## Volumes and Persistence

### Persistent Volumes
- `postgres_data`: PostgreSQL data
- `redis_data`: Redis data
- `rabbitmq_data`: RabbitMQ data

### Mounted Directories
- `./logs`: Application logs
- `./uploads`: File uploads
- `./backups`: Database backups (production)

## Monitoring and Logging

### Container Logs
```bash
# View all logs
docker-compose logs

# Follow specific service logs
docker-compose logs -f api

# View recent logs
docker-compose logs --tail=100 worker
```

### Health Monitoring
```bash
# Check container status
docker-compose ps

# Check resource usage
docker stats

# Run health checks
./scripts/test-docker-deployment.sh
```

## Troubleshooting

### Common Issues

1. **Port Conflicts**
   ```bash
   # Check port usage
   lsof -i :8000
   
   # Use different ports
   docker-compose up -d -p 8001:8000
   ```

2. **Memory Issues**
   ```bash
   # Check memory usage
   docker stats
   
   # Reduce resource limits in docker-compose.yml
   ```

3. **Database Connection Issues**
   ```bash
   # Check database logs
   docker-compose logs postgres
   
   # Test connection
   docker-compose exec postgres pg_isready -U kyc_user
   ```

4. **Worker Not Processing Tasks**
   ```bash
   # Check worker logs
   docker-compose logs worker
   
   # Restart worker
   docker-compose restart worker
   ```

### Debug Mode
```bash
# Run with debug logging
docker-compose up -d
docker-compose exec api python -c "import app.main; print('App loaded successfully')"
```

## Security Considerations

### Production Security
- Change all default passwords
- Use environment-specific secrets
- Enable TLS/SSL termination
- Configure firewall rules
- Regular security updates

### Network Security
- Use custom Docker networks
- Restrict container communication
- Enable container security scanning
- Monitor network traffic

## Backup and Recovery

### Database Backup
```bash
# Create backup
docker-compose exec postgres pg_dump -U kyc_user kyc_db > backup.sql

# Restore backup
docker-compose exec -T postgres psql -U kyc_user kyc_db < backup.sql
```

### Volume Backup
```bash
# Backup volumes
docker run --rm -v postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres_backup.tar.gz /data
```

## Performance Tuning

### Scaling Services
```bash
# Scale workers
docker-compose up -d --scale worker=5

# Scale API instances
docker-compose up -d --scale api=3
```

### Resource Optimization
- Adjust memory limits based on usage
- Use multi-stage builds for smaller images
- Enable Docker BuildKit for faster builds
- Use .dockerignore to reduce build context

## Maintenance

### Updates
```bash
# Pull latest images
docker-compose pull

# Rebuild and restart
docker-compose up -d --build

# Clean up old images
docker image prune -f
```

### Log Rotation
```bash
# Configure log rotation in docker-compose.yml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```