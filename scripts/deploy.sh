#!/bin/bash
# =============================================================================
# Forex Bot Deployment Script
# Deploy the full stack to production/staging
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$PROJECT_ROOT/docker"

# Default values
ENVIRONMENT="production"
BUILD_ONLY=false
NO_CACHE=false
DETACH=true

# Functions
print_banner() {
    echo -e "${BLUE}"
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║            LIGHTNING FOREX BOT - DEPLOYMENT               ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

show_help() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -e, --env         Environment (production|staging|dev) [default: production]"
    echo "  -b, --build-only  Build images without starting containers"
    echo "  --no-cache        Build without using cache"
    echo "  --no-detach       Run in foreground (don't detach)"
    echo "  -h, --help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                           # Deploy to production"
    echo "  $0 -e dev                    # Deploy to development"
    echo "  $0 --no-cache                # Rebuild without cache"
    echo "  $0 -b                        # Build images only"
}

check_requirements() {
    log_info "Checking requirements..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi

    # Check .env file
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        log_warn ".env file not found, copying from .env.example"
        if [ -f "$PROJECT_ROOT/.env.example" ]; then
            cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/.env"
            log_warn "Please update .env with your actual credentials before running in production"
        else
            log_error "Neither .env nor .env.example found"
            exit 1
        fi
    fi

    log_info "All requirements satisfied"
}

pre_deploy_checks() {
    log_info "Running pre-deployment checks..."

    # Check if containers are already running
    if docker-compose -f "$DOCKER_DIR/docker-compose.yml" ps -q 2>/dev/null | grep -q .; then
        log_warn "Existing containers detected"
        read -p "Do you want to stop and replace them? [y/N] " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            log_info "Stopping existing containers..."
            docker-compose -f "$DOCKER_DIR/docker-compose.yml" down
        else
            log_error "Deployment cancelled"
            exit 1
        fi
    fi

    # Verify required directories exist
    mkdir -p "$PROJECT_ROOT/data"
    mkdir -p "$PROJECT_ROOT/logs"
    mkdir -p "$PROJECT_ROOT/data/models"

    log_info "Pre-deployment checks passed"
}

build_images() {
    log_info "Building Docker images..."

    BUILD_ARGS=""
    if [ "$NO_CACHE" = true ]; then
        BUILD_ARGS="--no-cache"
    fi

    if [ "$ENVIRONMENT" = "dev" ]; then
        docker-compose -f "$DOCKER_DIR/docker-compose.yml" -f "$DOCKER_DIR/docker-compose.dev.yml" build $BUILD_ARGS
    else
        docker-compose -f "$DOCKER_DIR/docker-compose.yml" build $BUILD_ARGS
    fi

    log_info "Images built successfully"
}

deploy() {
    log_info "Starting deployment to $ENVIRONMENT environment..."

    UP_ARGS=""
    if [ "$DETACH" = true ]; then
        UP_ARGS="-d"
    fi

    if [ "$ENVIRONMENT" = "dev" ]; then
        docker-compose -f "$DOCKER_DIR/docker-compose.yml" -f "$DOCKER_DIR/docker-compose.dev.yml" up $UP_ARGS --build
    else
        docker-compose -f "$DOCKER_DIR/docker-compose.yml" up $UP_ARGS --build
    fi

    log_info "Deployment completed"
}

post_deploy_checks() {
    log_info "Running post-deployment checks..."

    # Wait for services to be healthy
    sleep 5

    # Check bot container
    if docker-compose -f "$DOCKER_DIR/docker-compose.yml" ps | grep -q "forex-bot.*running"; then
        log_info "Bot container is running"
    else
        log_warn "Bot container may not be running properly"
    fi

    # Check API health
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null | grep -q "200"; then
        log_info "API is healthy"
    else
        log_warn "API health check failed (may still be starting)"
    fi

    # Check database connection
    if docker-compose -f "$DOCKER_DIR/docker-compose.yml" exec -T postgres pg_isready -U lightning -d lightning_bot &>/dev/null; then
        log_info "Database is ready"
    else
        log_warn "Database may not be ready"
    fi

    # Check Redis
    if docker-compose -f "$DOCKER_DIR/docker-compose.yml" exec -T redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
        log_info "Redis is ready"
    else
        log_warn "Redis may not be ready"
    fi
}

show_status() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}Deployment Status:${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    docker-compose -f "$DOCKER_DIR/docker-compose.yml" ps
    echo ""
    echo -e "${GREEN}Services:${NC}"
    echo "  - API:      http://localhost:8000"
    echo "  - API Docs: http://localhost:8000/docs"
    echo "  - Postgres: localhost:5432"
    echo "  - Redis:    localhost:6379"
    echo ""
    echo -e "${GREEN}Useful Commands:${NC}"
    echo "  View logs:   docker-compose -f $DOCKER_DIR/docker-compose.yml logs -f"
    echo "  Stop:        docker-compose -f $DOCKER_DIR/docker-compose.yml down"
    echo "  Restart:     docker-compose -f $DOCKER_DIR/docker-compose.yml restart"
    echo ""
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -b|--build-only)
            BUILD_ONLY=true
            shift
            ;;
        --no-cache)
            NO_CACHE=true
            shift
            ;;
        --no-detach)
            DETACH=false
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Main execution
print_banner
check_requirements
pre_deploy_checks
build_images

if [ "$BUILD_ONLY" = true ]; then
    log_info "Build complete (--build-only specified, not starting containers)"
    exit 0
fi

deploy

if [ "$DETACH" = true ]; then
    post_deploy_checks
    show_status
fi

log_info "Deployment script finished"
