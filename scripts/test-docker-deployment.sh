#!/bin/bash
# Test script for Docker deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Testing KYC/AML microservice Docker deployment...${NC}"

# Test 1: Check if all containers are running
echo -e "${YELLOW}Test 1: Checking container status...${NC}"
if docker-compose ps | grep -q "Up.*healthy"; then
    echo -e "${GREEN}✓ Containers are running and healthy${NC}"
else
    echo -e "${RED}✗ Some containers are not healthy${NC}"
    docker-compose ps
    exit 1
fi

# Test 2: Test API health endpoint
echo -e "${YELLOW}Test 2: Testing API health endpoint...${NC}"
if curl -f -s http://localhost:8000/health > /dev/null; then
    echo -e "${GREEN}✓ API health endpoint is responding${NC}"
else
    echo -e "${RED}✗ API health endpoint is not responding${NC}"
    exit 1
fi

# Test 3: Test API documentation
echo -e "${YELLOW}Test 3: Testing API documentation...${NC}"
if curl -f -s http://localhost:8000/docs > /dev/null; then
    echo -e "${GREEN}✓ API documentation is accessible${NC}"
else
    echo -e "${RED}✗ API documentation is not accessible${NC}"
    exit 1
fi

# Test 4: Test database connectivity
echo -e "${YELLOW}Test 4: Testing database connectivity...${NC}"
if docker-compose exec -T postgres pg_isready -U kyc_user -d kyc_db > /dev/null; then
    echo -e "${GREEN}✓ Database is accessible${NC}"
else
    echo -e "${RED}✗ Database is not accessible${NC}"
    exit 1
fi

# Test 5: Test Redis connectivity
echo -e "${YELLOW}Test 5: Testing Redis connectivity...${NC}"
if docker-compose exec -T redis redis-cli ping | grep -q "PONG"; then
    echo -e "${GREEN}✓ Redis is accessible${NC}"
else
    echo -e "${RED}✗ Redis is not accessible${NC}"
    exit 1
fi

# Test 6: Test RabbitMQ connectivity
echo -e "${YELLOW}Test 6: Testing RabbitMQ connectivity...${NC}"
if docker-compose exec -T rabbitmq rabbitmq-diagnostics ping > /dev/null; then
    echo -e "${GREEN}✓ RabbitMQ is accessible${NC}"
else
    echo -e "${RED}✗ RabbitMQ is not accessible${NC}"
    exit 1
fi

# Test 7: Test Celery worker
echo -e "${YELLOW}Test 7: Testing Celery worker...${NC}"
if docker-compose exec -T worker celery -A app.worker inspect ping | grep -q "pong"; then
    echo -e "${GREEN}✓ Celery worker is responding${NC}"
else
    echo -e "${RED}✗ Celery worker is not responding${NC}"
    exit 1
fi

# Test 8: Test container resource limits
echo -e "${YELLOW}Test 8: Checking container resource usage...${NC}"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | head -7

# Test 9: Test container logs for errors
echo -e "${YELLOW}Test 9: Checking for errors in container logs...${NC}"
if docker-compose logs --tail=50 | grep -i "error\|exception\|failed" | grep -v "health check" | head -5; then
    echo -e "${YELLOW}⚠ Found some errors in logs (check above)${NC}"
else
    echo -e "${GREEN}✓ No critical errors found in recent logs${NC}"
fi

# Test 10: Test API endpoints
echo -e "${YELLOW}Test 10: Testing API endpoints...${NC}"

# Test health endpoint response
HEALTH_RESPONSE=$(curl -s http://localhost:8000/health)
if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    echo -e "${GREEN}✓ Health endpoint returns correct response${NC}"
else
    echo -e "${RED}✗ Health endpoint response is incorrect${NC}"
    echo "Response: $HEALTH_RESPONSE"
    exit 1
fi

echo -e "${GREEN}All tests passed! Docker deployment is working correctly.${NC}"

echo -e "${YELLOW}Service URLs:${NC}"
echo "  API: http://localhost:8000"
echo "  API Docs: http://localhost:8000/docs"
echo "  RabbitMQ Management: http://localhost:15672 (guest/guest)"
echo "  Flower (if available): http://localhost:5555"

echo -e "${YELLOW}Useful commands:${NC}"
echo "  View logs: docker-compose logs -f [service]"
echo "  Stop services: docker-compose down"
echo "  Restart services: docker-compose restart"
echo "  Scale workers: docker-compose up -d --scale worker=3"