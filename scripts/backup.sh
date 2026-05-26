#!/bin/bash
# =============================================================================
# Forex Bot Backup Script
# Backup PostgreSQL database and important data
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
BACKUP_DIR="$PROJECT_ROOT/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Database config (from docker-compose)
DB_USER="lightning"
DB_NAME="lightning_bot"
DB_CONTAINER="forex-postgres"

# Retention settings
KEEP_DAYS=30
MAX_BACKUPS=50

log_info() {
    echo -e "${GREEN}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

show_help() {
    echo "Usage: $0 [OPTIONS] [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  backup    - Create a new backup (default)"
    echo "  restore   - Restore from a backup file"
    echo "  list      - List available backups"
    echo "  cleanup   - Remove old backups"
    echo ""
    echo "Options:"
    echo "  -o, --output DIR    Backup output directory [default: ./backups]"
    echo "  -f, --file FILE     Backup file for restore"
    echo "  --keep-days NUM     Keep backups for NUM days [default: 30]"
    echo "  --models            Include ML model files in backup"
    echo "  --full              Full backup (database + models + logs)"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                          # Create database backup"
    echo "  $0 --full                   # Full backup"
    echo "  $0 restore -f backup.sql.gz # Restore from file"
    echo "  $0 list                     # List backups"
    echo "  $0 cleanup                  # Remove old backups"
}

check_prerequisites() {
    # Check if postgres container is running
    if ! docker ps --format '{{.Names}}' | grep -q "$DB_CONTAINER"; then
        log_error "PostgreSQL container ($DB_CONTAINER) is not running"
        log_info "Start the containers with: ./scripts/deploy.sh"
        exit 1
    fi

    # Create backup directory
    mkdir -p "$BACKUP_DIR"
}

backup_database() {
    log_info "Starting PostgreSQL backup..."

    BACKUP_FILE="$BACKUP_DIR/db_backup_${DATE}.sql"
    BACKUP_FILE_GZ="${BACKUP_FILE}.gz"

    # Create backup using pg_dump
    docker exec -t "$DB_CONTAINER" pg_dump -U "$DB_USER" -d "$DB_NAME" \
        --verbose --format=plain --no-owner --no-privileges \
        > "$BACKUP_FILE" 2>/dev/null

    if [ $? -eq 0 ]; then
        # Compress backup
        gzip "$BACKUP_FILE"

        BACKUP_SIZE=$(du -h "$BACKUP_FILE_GZ" | cut -f1)
        log_info "Database backup created: $BACKUP_FILE_GZ ($BACKUP_SIZE)"
        echo "$BACKUP_FILE_GZ"
    else
        log_error "Database backup failed"
        rm -f "$BACKUP_FILE"
        exit 1
    fi
}

backup_models() {
    log_info "Backing up ML models..."

    MODELS_DIR="$PROJECT_ROOT/data/models"
    MODELS_BACKUP="$BACKUP_DIR/models_backup_${DATE}.tar.gz"

    if [ -d "$MODELS_DIR" ] && [ "$(ls -A $MODELS_DIR 2>/dev/null)" ]; then
        tar -czf "$MODELS_BACKUP" -C "$PROJECT_ROOT/data" models
        BACKUP_SIZE=$(du -h "$MODELS_BACKUP" | cut -f1)
        log_info "Models backup created: $MODELS_BACKUP ($BACKUP_SIZE)"
    else
        log_warn "No models found to backup"
    fi
}

backup_logs() {
    log_info "Backing up logs..."

    LOGS_DIR="$PROJECT_ROOT/logs"
    LOGS_BACKUP="$BACKUP_DIR/logs_backup_${DATE}.tar.gz"

    if [ -d "$LOGS_DIR" ] && [ "$(ls -A $LOGS_DIR 2>/dev/null)" ]; then
        tar -czf "$LOGS_BACKUP" -C "$PROJECT_ROOT" logs
        BACKUP_SIZE=$(du -h "$LOGS_BACKUP" | cut -f1)
        log_info "Logs backup created: $LOGS_BACKUP ($BACKUP_SIZE)"
    else
        log_warn "No logs found to backup"
    fi
}

full_backup() {
    log_info "Creating full backup..."

    FULL_BACKUP_DIR="$BACKUP_DIR/full_backup_${DATE}"
    mkdir -p "$FULL_BACKUP_DIR"

    # Backup database
    DB_FILE=$(backup_database)
    mv "$DB_FILE" "$FULL_BACKUP_DIR/"

    # Backup models
    MODELS_DIR="$PROJECT_ROOT/data/models"
    if [ -d "$MODELS_DIR" ] && [ "$(ls -A $MODELS_DIR 2>/dev/null)" ]; then
        cp -r "$MODELS_DIR" "$FULL_BACKUP_DIR/"
    fi

    # Backup config
    cp "$PROJECT_ROOT/.env.example" "$FULL_BACKUP_DIR/" 2>/dev/null || true
    cp -r "$PROJECT_ROOT/config" "$FULL_BACKUP_DIR/" 2>/dev/null || true

    # Create archive
    FULL_ARCHIVE="$BACKUP_DIR/full_backup_${DATE}.tar.gz"
    tar -czf "$FULL_ARCHIVE" -C "$BACKUP_DIR" "full_backup_${DATE}"
    rm -rf "$FULL_BACKUP_DIR"

    BACKUP_SIZE=$(du -h "$FULL_ARCHIVE" | cut -f1)
    log_info "Full backup created: $FULL_ARCHIVE ($BACKUP_SIZE)"
}

restore_database() {
    if [ -z "$RESTORE_FILE" ]; then
        log_error "No backup file specified. Use -f or --file option."
        exit 1
    fi

    if [ ! -f "$RESTORE_FILE" ]; then
        log_error "Backup file not found: $RESTORE_FILE"
        exit 1
    fi

    log_warn "This will OVERWRITE the current database!"
    read -p "Are you sure you want to continue? [y/N] " -n 1 -r
    echo

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Restore cancelled"
        exit 0
    fi

    log_info "Restoring database from: $RESTORE_FILE"

    # Check if file is compressed
    if [[ "$RESTORE_FILE" == *.gz ]]; then
        gunzip -c "$RESTORE_FILE" | docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME"
    else
        cat "$RESTORE_FILE" | docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME"
    fi

    if [ $? -eq 0 ]; then
        log_info "Database restored successfully"
    else
        log_error "Database restore failed"
        exit 1
    fi
}

list_backups() {
    echo -e "${BLUE}Available Backups:${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    if [ -d "$BACKUP_DIR" ] && [ "$(ls -A $BACKUP_DIR 2>/dev/null)" ]; then
        ls -lh "$BACKUP_DIR" | tail -n +2 | awk '{print $9, $5, $6, $7, $8}'
        echo ""
        TOTAL=$(du -sh "$BACKUP_DIR" | cut -f1)
        COUNT=$(ls -1 "$BACKUP_DIR" | wc -l | tr -d ' ')
        echo -e "Total: ${GREEN}$COUNT${NC} backups, ${GREEN}$TOTAL${NC}"
    else
        echo "No backups found in $BACKUP_DIR"
    fi
}

cleanup_backups() {
    log_info "Cleaning up old backups (keeping last $KEEP_DAYS days)..."

    if [ -d "$BACKUP_DIR" ]; then
        # Remove files older than KEEP_DAYS
        DELETED=$(find "$BACKUP_DIR" -type f -mtime +$KEEP_DAYS -print -delete | wc -l | tr -d ' ')
        log_info "Removed $DELETED old backup files"

        # Also enforce MAX_BACKUPS limit
        CURRENT_COUNT=$(ls -1 "$BACKUP_DIR" 2>/dev/null | wc -l | tr -d ' ')
        if [ "$CURRENT_COUNT" -gt "$MAX_BACKUPS" ]; then
            TO_DELETE=$((CURRENT_COUNT - MAX_BACKUPS))
            log_info "Removing $TO_DELETE excess backups (keeping $MAX_BACKUPS)"
            ls -1t "$BACKUP_DIR" | tail -n "$TO_DELETE" | xargs -I {} rm "$BACKUP_DIR/{}"
        fi
    fi
}

# Default command
COMMAND="backup"
INCLUDE_MODELS=false
FULL=false
RESTORE_FILE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        backup|restore|list|cleanup)
            COMMAND="$1"
            shift
            ;;
        -o|--output)
            BACKUP_DIR="$2"
            shift 2
            ;;
        -f|--file)
            RESTORE_FILE="$2"
            shift 2
            ;;
        --keep-days)
            KEEP_DAYS="$2"
            shift 2
            ;;
        --models)
            INCLUDE_MODELS=true
            shift
            ;;
        --full)
            FULL=true
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

# Execute command
echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║            LIGHTNING FOREX BOT - BACKUP                   ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

case $COMMAND in
    backup)
        check_prerequisites
        if [ "$FULL" = true ]; then
            full_backup
        else
            backup_database
            if [ "$INCLUDE_MODELS" = true ]; then
                backup_models
            fi
        fi
        cleanup_backups
        ;;
    restore)
        check_prerequisites
        restore_database
        ;;
    list)
        list_backups
        ;;
    cleanup)
        cleanup_backups
        ;;
esac

log_info "Backup script completed"
