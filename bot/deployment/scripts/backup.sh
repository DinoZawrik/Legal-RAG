#!/bin/bash
# =============================================================================
# LegalRAG - Backup and Restore Script
# =============================================================================
#
# This script creates comprehensive backups of the LegalRAG system including
# databases, configurations, and application state
# 
# Usage:
#   ./backup.sh [options]
#
# Options:
#   --auto               Run automatic backup (no prompts)
#   --restore BACKUP     Restore from specific backup
#   --list               List available backups
#   --cleanup            Clean old backups (keep last 10)
#   --config-only        Backup only configuration files
#   --help               Show this help message
#
# Examples:
#   ./backup.sh                                    # Interactive backup
#   ./backup.sh --auto                             # Automatic backup
#   ./backup.sh --restore backup-2024-01-15-12-30 # Restore specific backup
#   ./backup.sh --list                             # List backups
#   ./backup.sh --cleanup                          # Clean old backups
#
# =============================================================================

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default backup location
BACKUP_BASE_DIR="${BACKUP_BASE_DIR:-/opt/legalrag/backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
MAX_BACKUPS_TO_KEEP="${MAX_BACKUPS_TO_KEEP:-10}"

# Backup timestamp
TIMESTAMP=$(date +"%Y-%m-%d-%H-%M")
BACKUP_NAME="backup-${TIMESTAMP}"
BACKUP_DIR="${BACKUP_BASE_DIR}/${BACKUP_NAME}"

# Docker compose configuration
COMPOSE_FILE="docker-compose.prod.yml"

# Database configuration (from .env.production)
DB_HOST="${POSTGRES_HOST:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-legalrag_db}"
DB_USER="${POSTGRES_USER:-legalrag_user}"
DB_PASSWORD="${POSTGRES_PASSWORD:-}"

REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_DB="${REDIS_DB:-0}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Operation modes
AUTO_MODE="false"
RESTORE_MODE="false"
LIST_MODE="false"
CLEANUP_MODE="false"
CONFIG_ONLY="false"
RESTORE_BACKUP=""

# =============================================================================
# FUNCTIONS
# =============================================================================

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] ⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ❌ $1${NC}"
}

show_help() {
    cat << EOF
LegalRAG - Backup and Restore Script

Usage: $0 [options]

Options:
    --auto               Run automatic backup (no prompts)
    --restore BACKUP     Restore from specific backup
    --list               List available backups
    --cleanup            Clean old backups (keep last $MAX_BACKUPS_TO_KEEP)
    --config-only        Backup only configuration files
    --help               Show this help message

Examples:
    $0                                    # Interactive backup
    $0 --auto                             # Automatic backup
    $0 --restore backup-2024-01-15-12-30 # Restore specific backup
    $0 --list                             # List backups
    $0 --cleanup                          # Clean old backups

Backup includes:
    - PostgreSQL database dump
    - Redis data dump
    - Configuration files (.env.*, docker-compose.*)
    - Application logs
    - System information snapshot

EOF
}

check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check required commands
    local required_commands=("docker" "docker-compose" "pg_dump" "redis-cli")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            log_error "Required command '$cmd' not found"
            exit 1
        fi
    done
    
    # Check if Docker is running
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
    
    # Create backup directory if it doesn't exist
    if [[ ! -d "$BACKUP_BASE_DIR" ]]; then
        sudo mkdir -p "$BACKUP_BASE_DIR"
        sudo chown $(whoami):$(whoami) "$BACKUP_BASE_DIR"
    fi
    
    log_success "Prerequisites check passed"
}

load_environment() {
    log "Loading environment configuration..."
    
    local env_file="$PROJECT_ROOT/.env.production"
    if [[ -f "$env_file" ]]; then
        # Source environment file safely
        set -a
        source "$env_file"
        set +a
        log_success "Environment loaded from $env_file"
    else
        log_warning "Environment file not found: $env_file"
    fi
}

create_backup_directory() {
    log "Creating backup directory: $BACKUP_DIR"
    
    if [[ -d "$BACKUP_DIR" ]]; then
        if [[ "$AUTO_MODE" == "false" ]]; then
            read -p "Backup directory already exists. Overwrite? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                log "Backup cancelled"
                exit 0
            fi
        fi
        rm -rf "$BACKUP_DIR"
    fi
    
    mkdir -p "$BACKUP_DIR"/{databases,config,logs,system}
    log_success "Backup directory created"
}

backup_postgresql() {
    log "Backing up PostgreSQL database..."
    
    local backup_file="$BACKUP_DIR/databases/postgres_${DB_NAME}.sql"
    local container_name="legalrag_postgres_prod"
    
    # Check if PostgreSQL container is running
    if docker ps | grep -q "$container_name"; then
        # Backup using docker exec
        if docker exec "$container_name" pg_dump -U "$DB_USER" "$DB_NAME" > "$backup_file"; then
            local backup_size=$(du -h "$backup_file" | cut -f1)
            log_success "PostgreSQL backup completed ($backup_size)"
        else
            log_error "PostgreSQL backup failed"
            return 1
        fi
    else
        log_warning "PostgreSQL container not running, skipping database backup"
    fi
}

backup_redis() {
    log "Backing up Redis data..."
    
    local backup_file="$BACKUP_DIR/databases/redis.rdb"
    local container_name="legalrag_redis_prod"
    
    # Check if Redis container is running
    if docker ps | grep -q "$container_name"; then
        # Force Redis to save current state
        docker exec "$container_name" redis-cli BGSAVE
        
        # Wait for background save to complete
        local max_attempts=30
        local attempt=1
        while [[ $attempt -le $max_attempts ]]; do
            if docker exec "$container_name" redis-cli LASTSAVE | grep -q "$(date +%s)"; then
                break
            fi
            sleep 1
            attempt=$((attempt + 1))
        done
        
        # Copy the RDB file
        if docker cp "$container_name:/data/dump.rdb" "$backup_file"; then
            local backup_size=$(du -h "$backup_file" | cut -f1)
            log_success "Redis backup completed ($backup_size)"
        else
            log_error "Redis backup failed"
            return 1
        fi
    else
        log_warning "Redis container not running, skipping Redis backup"
    fi
}

backup_configuration() {
    log "Backing up configuration files..."
    
    cd "$PROJECT_ROOT"
    
    # Backup environment files
    cp -f .env* "$BACKUP_DIR/config/" 2>/dev/null || true
    
    # Backup Docker Compose files
    cp -f docker-compose*.yml "$BACKUP_DIR/config/" 2>/dev/null || true
    
    # Backup Dockerfile
    cp -f Dockerfile* "$BACKUP_DIR/config/" 2>/dev/null || true
    
    # Backup deployment configuration
    if [[ -d "deployment" ]]; then
        cp -r deployment "$BACKUP_DIR/config/"
    fi
    
    # Backup nginx configuration
    if [[ -d "nginx" ]]; then
        cp -r nginx "$BACKUP_DIR/config/"
    fi
    
    log_success "Configuration files backed up"
}

backup_logs() {
    log "Backing up application logs..."
    
    cd "$PROJECT_ROOT"
    
    # Backup Docker container logs
    local services=($(docker-compose -f "$COMPOSE_FILE" config --services 2>/dev/null || echo ""))
    
    for service in "${services[@]}"; do
        if docker ps | grep -q "$service"; then
            local log_file="$BACKUP_DIR/logs/${service}.log"
            docker logs "$service" > "$log_file" 2>&1 || true
        fi
    done
    
    # Backup system logs if accessible
    if [[ -r /var/log/syslog ]]; then
        grep -i "legalrag\|docker" /var/log/syslog | tail -1000 > "$BACKUP_DIR/logs/system.log" 2>/dev/null || true
    fi
    
    log_success "Logs backed up"
}

backup_system_info() {
    log "Collecting system information..."
    
    local info_file="$BACKUP_DIR/system/system_info.txt"
    
    {
        echo "=== LegalRAG Backup Report ==="
        echo "Backup Date: $(date)"
        echo "Backup Name: $BACKUP_NAME"
        echo "System: $(uname -a)"
        echo ""
        echo "=== Docker Information ==="
        docker --version
        docker-compose --version
        echo ""
        echo "=== Running Containers ==="
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
        echo ""
        echo "=== Disk Usage ==="
        df -h /
        echo ""
        echo "=== Memory Usage ==="
        free -h
        echo ""
        echo "=== Network ==="
        ss -tuln
        echo ""
    } > "$info_file"
    
    # Backup docker-compose configuration
    cd "$PROJECT_ROOT"
    docker-compose -f "$COMPOSE_FILE" config > "$BACKUP_DIR/system/docker-compose-resolved.yml" 2>/dev/null || true
    
    log_success "System information collected"
}

create_backup_manifest() {
    log "Creating backup manifest..."
    
    local manifest_file="$BACKUP_DIR/MANIFEST.json"
    local backup_size=$(du -sh "$BACKUP_DIR" | cut -f1)
    
    cat > "$manifest_file" << EOF
{
  "backup_name": "$BACKUP_NAME",
  "timestamp": "$(date -Iseconds)",
  "version": "4.0",
  "system": {
    "hostname": "$(hostname)",
    "os": "$(uname -s)",
    "kernel": "$(uname -r)",
    "architecture": "$(uname -m)"
  },
  "components": {
    "postgresql": $(docker ps | grep -q "legalrag_postgres_prod" && echo "true" || echo "false"),
    "redis": $(docker ps | grep -q "legalrag_redis_prod" && echo "true" || echo "false"),
    "microservices": $(docker ps | grep -q "legalrag-microservices" && echo "true" || echo "false"),
    "telegram_bot": $(docker ps | grep -q "legalrag-telegram-bot" && echo "true" || echo "false")
  },
  "backup_size": "$backup_size",
  "files": [
$(find "$BACKUP_DIR" -type f -exec basename {} \; | sed 's/.*/"&"/' | paste -sd, -)
  ]
}
EOF
    
    log_success "Backup manifest created"
}

compress_backup() {
    if [[ "$AUTO_MODE" == "false" ]]; then
        read -p "Compress backup? (Y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            return 0
        fi
    fi
    
    log "Compressing backup..."
    
    cd "$BACKUP_BASE_DIR"
    tar -czf "${BACKUP_NAME}.tar.gz" "$BACKUP_NAME"
    
    local compressed_size=$(du -h "${BACKUP_NAME}.tar.gz" | cut -f1)
    local original_size=$(du -h "$BACKUP_NAME" | cut -f1)
    
    log_success "Backup compressed: $original_size → $compressed_size"
    
    # Remove uncompressed backup
    rm -rf "$BACKUP_NAME"
    
    echo
    log_success "Backup completed: ${BACKUP_BASE_DIR}/${BACKUP_NAME}.tar.gz"
}

list_backups() {
    log "Available backups in $BACKUP_BASE_DIR:"
    echo
    
    if [[ ! -d "$BACKUP_BASE_DIR" ]] || [[ -z "$(ls -A "$BACKUP_BASE_DIR" 2>/dev/null)" ]]; then
        log_warning "No backups found"
        return 0
    fi
    
    local backups=($(ls -1t "$BACKUP_BASE_DIR"/ | grep -E "^backup-"))
    
    printf "%-30s %-15s %-10s %-15s\n" "BACKUP NAME" "SIZE" "AGE" "TYPE"
    printf "%-30s %-15s %-10s %-15s\n" "$(printf '%*s' 30 | tr ' ' '-')" "$(printf '%*s' 15 | tr ' ' '-')" "$(printf '%*s' 10 | tr ' ' '-')" "$(printf '%*s' 15 | tr ' ' '-')"
    
    for backup in "${backups[@]}"; do
        local backup_path="$BACKUP_BASE_DIR/$backup"
        local size age type
        
        if [[ -f "$backup_path" ]]; then
            size=$(du -h "$backup_path" | cut -f1)
            age=$(stat -f "%Sm" -t "%Y-%m-%d" "$backup_path" 2>/dev/null || stat -c "%y" "$backup_path" | cut -d' ' -f1)
            type="compressed"
        elif [[ -d "$backup_path" ]]; then
            size=$(du -h "$backup_path" | tail -1 | cut -f1)
            age=$(stat -f "%Sm" -t "%Y-%m-%d" "$backup_path" 2>/dev/null || stat -c "%y" "$backup_path" | cut -d' ' -f1)
            type="directory"
        else
            continue
        fi
        
        printf "%-30s %-15s %-10s %-15s\n" "$backup" "$size" "$age" "$type"
    done
}

cleanup_old_backups() {
    log "Cleaning up old backups..."
    
    cd "$BACKUP_BASE_DIR"
    
    # Remove backups older than retention days
    find . -name "backup-*" -type f -mtime +${BACKUP_RETENTION_DAYS} -delete 2>/dev/null || true
    find . -name "backup-*" -type d -mtime +${BACKUP_RETENTION_DAYS} -exec rm -rf {} + 2>/dev/null || true
    
    # Keep only the most recent backups
    local backups=($(ls -1t | grep -E "^backup-" | head -n +${MAX_BACKUPS_TO_KEEP}))
    local all_backups=($(ls -1 | grep -E "^backup-"))
    
    for backup in "${all_backups[@]}"; do
        local keep=false
        for keep_backup in "${backups[@]}"; do
            if [[ "$backup" == "$keep_backup" ]]; then
                keep=true
                break
            fi
        done
        
        if [[ "$keep" == "false" ]]; then
            log "Removing old backup: $backup"
            rm -rf "$backup"
        fi
    done
    
    log_success "Cleanup completed"
}

restore_backup() {
    local backup_name="$1"
    local backup_path="$BACKUP_BASE_DIR/$backup_name"
    
    log "Restoring backup: $backup_name"
    
    # Check if backup exists
    if [[ ! -e "$backup_path" && ! -e "$backup_path.tar.gz" ]]; then
        log_error "Backup not found: $backup_name"
        exit 1
    fi
    
    # Extract if compressed
    if [[ -f "$backup_path.tar.gz" ]]; then
        log "Extracting compressed backup..."
        cd "$BACKUP_BASE_DIR"
        tar -xzf "$backup_path.tar.gz"
        backup_path="$BACKUP_BASE_DIR/$backup_name"
    fi
    
    if [[ ! -d "$backup_path" ]]; then
        log_error "Invalid backup format"
        exit 1
    fi
    
    # Confirmation prompt
    if [[ "$AUTO_MODE" == "false" ]]; then
        echo
        log_warning "This will REPLACE current system state with backup data!"
        read -p "Continue with restore? (yes/no): " -r
        if [[ ! $REPLY == "yes" ]]; then
            log "Restore cancelled"
            exit 0
        fi
    fi
    
    # Stop services
    log "Stopping services..."
    cd "$PROJECT_ROOT"
    docker-compose -f "$COMPOSE_FILE" down --timeout 60 || true
    
    # Restore configuration
    log "Restoring configuration..."
    if [[ -d "$backup_path/config" ]]; then
        cp -f "$backup_path/config"/.env* "$PROJECT_ROOT/" 2>/dev/null || true
        cp -f "$backup_path/config"/docker-compose*.yml "$PROJECT_ROOT/" 2>/dev/null || true
    fi
    
    # Start infrastructure services
    log "Starting infrastructure services..."
    docker-compose -f "$COMPOSE_FILE" up -d postgres redis chromadb
    sleep 15
    
    # Restore PostgreSQL
    if [[ -f "$backup_path/databases/postgres_${DB_NAME}.sql" ]]; then
        log "Restoring PostgreSQL database..."
        docker exec -i legalrag_postgres_prod psql -U "$DB_USER" -d "$DB_NAME" < "$backup_path/databases/postgres_${DB_NAME}.sql"
        log_success "PostgreSQL restored"
    fi
    
    # Restore Redis
    if [[ -f "$backup_path/databases/redis.rdb" ]]; then
        log "Restoring Redis data..."
        docker cp "$backup_path/databases/redis.rdb" legalrag_redis_prod:/data/dump.rdb
        docker restart legalrag_redis_prod
        sleep 5
        log_success "Redis restored"
    fi
    
    # Start application services
    log "Starting application services..."
    docker-compose -f "$COMPOSE_FILE" up -d
    
    log_success "Backup restored successfully!"
    log "Please verify system functionality"
}

# =============================================================================
# MAIN SCRIPT
# =============================================================================

perform_backup() {
    log "Starting LegalRAG backup..."
    
    check_prerequisites
    load_environment
    create_backup_directory
    
    if [[ "$CONFIG_ONLY" == "true" ]]; then
        log "Running configuration-only backup..."
        backup_configuration
        backup_system_info
    else
        log "Running full system backup..."
        backup_postgresql
        backup_redis
        backup_configuration
        backup_logs
        backup_system_info
    fi
    
    create_backup_manifest
    
    if [[ "$AUTO_MODE" == "false" ]]; then
        compress_backup
    else
        log "Auto mode: skipping compression"
    fi
    
    local final_path="$BACKUP_DIR"
    if [[ -f "${BACKUP_DIR}.tar.gz" ]]; then
        final_path="${BACKUP_DIR}.tar.gz"
    fi
    
    echo
    log_success "Backup completed successfully!"
    log "Backup location: $final_path"
    log "Backup size: $(du -h "$final_path" | cut -f1)"
}

main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --auto)
                AUTO_MODE="true"
                shift
                ;;
            --restore)
                RESTORE_MODE="true"
                RESTORE_BACKUP="$2"
                shift 2
                ;;
            --list)
                LIST_MODE="true"
                shift
                ;;
            --cleanup)
                CLEANUP_MODE="true"
                shift
                ;;
            --config-only)
                CONFIG_ONLY="true"
                shift
                ;;
            --help)
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
    
    # Execute based on mode
    if [[ "$LIST_MODE" == "true" ]]; then
        list_backups
    elif [[ "$CLEANUP_MODE" == "true" ]]; then
        cleanup_old_backups
    elif [[ "$RESTORE_MODE" == "true" ]]; then
        restore_backup "$RESTORE_BACKUP"
    else
        perform_backup
    fi
}

# Run main function
main "$@"