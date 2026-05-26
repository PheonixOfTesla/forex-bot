#!/bin/bash
# =============================================================================
# Forex Bot Log Viewer
# View and filter logs from Docker containers
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$PROJECT_ROOT/docker"

# Default values
SERVICE="all"
FOLLOW=false
TAIL_LINES=100
SINCE=""
FILTER=""

show_help() {
    echo "Usage: $0 [OPTIONS] [SERVICE]"
    echo ""
    echo "Services:"
    echo "  bot       - Trading bot logs"
    echo "  api       - API server logs"
    echo "  postgres  - PostgreSQL logs"
    echo "  redis     - Redis logs"
    echo "  all       - All services (default)"
    echo ""
    echo "Options:"
    echo "  -f, --follow      Follow log output (stream)"
    echo "  -n, --lines NUM   Number of lines to show [default: 100]"
    echo "  --since TIME      Show logs since timestamp (e.g., '10m', '1h', '2023-01-01')"
    echo "  --filter TEXT     Filter logs containing TEXT"
    echo "  --errors          Show only ERROR and WARNING level logs"
    echo "  --trades          Show only trade-related logs"
    echo "  -h, --help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 bot                    # Show last 100 bot logs"
    echo "  $0 -f bot                 # Stream bot logs"
    echo "  $0 -n 500 api             # Show last 500 API logs"
    echo "  $0 --since 1h             # Show logs from last hour"
    echo "  $0 --errors               # Show only errors"
    echo "  $0 --filter 'EUR_USD'     # Filter for EUR_USD mentions"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -f|--follow)
            FOLLOW=true
            shift
            ;;
        -n|--lines)
            TAIL_LINES="$2"
            shift 2
            ;;
        --since)
            SINCE="$2"
            shift 2
            ;;
        --filter)
            FILTER="$2"
            shift 2
            ;;
        --errors)
            FILTER="ERROR\|WARNING\|CRITICAL"
            shift
            ;;
        --trades)
            FILTER="trade\|TRADE\|position\|POSITION\|order\|ORDER"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        bot|api|postgres|redis|all)
            SERVICE="$1"
            shift
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Build docker-compose command
CMD="docker-compose -f $DOCKER_DIR/docker-compose.yml logs"

# Add service if not all
if [ "$SERVICE" != "all" ]; then
    CMD="$CMD $SERVICE"
fi

# Add options
if [ "$FOLLOW" = true ]; then
    CMD="$CMD -f"
fi

if [ -n "$TAIL_LINES" ]; then
    CMD="$CMD --tail=$TAIL_LINES"
fi

if [ -n "$SINCE" ]; then
    CMD="$CMD --since=$SINCE"
fi

# Execute command
echo -e "${BLUE}Viewing logs for: ${SERVICE}${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ -n "$FILTER" ]; then
    $CMD 2>&1 | grep -E --color=always "$FILTER" || true
else
    $CMD
fi
