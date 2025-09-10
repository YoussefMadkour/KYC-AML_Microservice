#!/bin/bash
# Docker deployment script for KYC/AML microservice

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="development"
COMPOSE_FILE="docker-compose.yml"
BUILD_IMAGES=false
DETACHED=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -f|--file)
            COMPOSE_FILE="$2"
            shift 2
            ;;
        -b|--build)
            BUILD_IMAGES=true
            shift
            ;;
        -d|--detach)
            DETACHED=true
            shift
            ;;
        --prod)
            ENVIRONMENT="production"
            COMPOSE_FILE="docker-compose.prod.yml"
            shift
            ;;
        --tasks)
            ENVIRONMENT="tasks"
            COMPOSE_FILE="docker-compose.tasks.yml"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -e, --env ENV       Environment (development|production|tasks) [default: development]"
            echo "  -f, --file FILE     Docker compose file [default: docker-compose.yml]"
            echo "  -b, --build         Build images before starting"
            echo "  -d, --detach        Run in detached mode"
            echo "  --prod              Use production configuration"
            echo "  --tasks             Use tasks-only configuration"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option $1"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}Deploying KYC/AML microservice...${NC}"
echo -e "${YELLOW}Environment: $ENVIRONMENT${NC}"
echo -e "${YELLOW}Compose file: $COMPOSE_FILE${NC}"

# Check if compose file exists
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}Error: Compose file $COMPOSE_FILE not found${NC}"
    exit 1
fi

# Create necessary directories
echo -e "${GREEN}Creating necessary directories...${NC}"
mkdir -p logs uploads backups

# Set appropriate permissions
chmod 755 logs uploads backups

# Build images if requested
if [ "$BUILD_IMAGES" = true ]; then
    echo -e "${GREEN}Building images...${NC}"
    docker-compose -f $COMPOSE_FILE build
fi

# Start services
echo -e "${GREEN}Starting services...${NC}"
if [ "$DETACHED" = true ]; then
    docker-compose -f $COMPOSE_FILE up -d
else
    docker-compose -f $COMPOSE_FILE up
fi

# Show status if running in detached mode
if [ "$DETACHED" = true ]; then
    echo -e "${GREEN}Services started successfully!${NC}"
    echo -e "${YELLOW}Service status:${NC}"
    docker-compose -f $COMPOSE_FILE ps
    
    echo -e "${YELLOW}Useful commands:${NC}"
    echo "  View logs: docker-compose -f $COMPOSE_FILE logs -f"
    echo "  Stop services: docker-compose -f $COMPOSE_FILE down"
    echo "  Restart services: docker-compose -f $COMPOSE_FILE restart"
    
    if [ "$ENVIRONMENT" = "development" ]; then
        echo -e "${YELLOW}Development URLs:${NC}"
        echo "  API: http://localhost:8000"
        echo "  API Docs: http://localhost:8000/docs"
        echo "  RabbitMQ Management: http://localhost:15672"
        echo "  Flower (Celery): http://localhost:5555"
    fi
fi