#!/bin/bash
# Docker build script for KYC/AML microservice

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
BUILD_TYPE="development"
PUSH_IMAGES=false
TAG="latest"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--type)
            BUILD_TYPE="$2"
            shift 2
            ;;
        -p|--push)
            PUSH_IMAGES=true
            shift
            ;;
        --tag)
            TAG="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  -t, --type TYPE     Build type (development|production) [default: development]"
            echo "  -p, --push          Push images to registry"
            echo "  --tag TAG           Docker image tag [default: latest]"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option $1"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}Building KYC/AML microservice Docker images...${NC}"
echo -e "${YELLOW}Build type: $BUILD_TYPE${NC}"
echo -e "${YELLOW}Tag: $TAG${NC}"

# Build main application image
echo -e "${GREEN}Building main application image...${NC}"
if [ "$BUILD_TYPE" = "production" ]; then
    docker build -t kyc-aml-microservice-api:$TAG --target production .
else
    docker build -t kyc-aml-microservice-api:$TAG .
fi

# Build worker image
echo -e "${GREEN}Building worker image...${NC}"
docker build -f Dockerfile.worker -t kyc-aml-microservice-worker:$TAG .

# Tag images with additional tags
if [ "$TAG" != "latest" ]; then
    docker tag kyc-aml-microservice-api:$TAG kyc-aml-microservice-api:latest
    docker tag kyc-aml-microservice-worker:$TAG kyc-aml-microservice-worker:latest
fi

# Push images if requested
if [ "$PUSH_IMAGES" = true ]; then
    echo -e "${GREEN}Pushing images to registry...${NC}"
    docker push kyc-aml-microservice-api:$TAG
    docker push kyc-aml-microservice-worker:$TAG
    
    if [ "$TAG" != "latest" ]; then
        docker push kyc-aml-microservice-api:latest
        docker push kyc-aml-microservice-worker:latest
    fi
fi

echo -e "${GREEN}Build completed successfully!${NC}"
echo -e "${YELLOW}Images built:${NC}"
echo "  - kyc-aml-microservice-api:$TAG"
echo "  - kyc-aml-microservice-worker:$TAG"

# Show image sizes
echo -e "${YELLOW}Image sizes:${NC}"
docker images | grep kyc-aml-microservice | head -2