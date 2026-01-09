#!/bin/bash
# =============================================================================
# LegalRAG - Production Deployment Script
# =============================================================================
# 
# This script automates the deployment process for LegalRAG
# 
# Usage:
#   ./deploy.sh [options]
#
# Options:
#   --env ENV        Environment to deploy (production, staging)
#   --backup         Create backup before deployment
#   --no-pull        Skip pulling latest images
#   --rollback       Rollback to previous version
#   --health-check   Run health checks after deployment
#   --help           Show this help message
#
# =============================================================================

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOYMENT_DIR="$PROJECT_ROOT/deployment"

# Default values
ENVIRONMENT="${ENVIRONMENT:-production}"
BACKUP_ENABLED="true"
PULL_IMAGES="true"
ROLLBACK_MODE="false"
HEALTH_CHECK="true"
COMPOSE_FILE="docker-compose.prod.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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
LegalRAG - Deployment Script

Usage: $0 [options]

Options:
    --env ENV        Environment to deploy (production, staging) [default: production]
    --backup         Create backup before deployment [default: enabled]
    --no-backup      Skip backup creation
    --no-pull        Skip pulling latest images
    --rollback       Rollback to previous version
    --health-check   Run health checks after deployment [default: enabled]
    --no-health      Skip health checks
    --help           Show this help message

Examples:
    $0                          # Standard production deployment
    $0 --env staging            # Deploy to staging
    $0 --no-backup --no-pull    # Quick deployment without backup/pull
    $0 --rollback               # Rollback to previous version

EOF
}

check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if running as correct user
    if [[ $(id -u) -eq 0 ]]; then
        log_error "This script should not be run as root for security reasons"
        exit 1
    fi
    
    # Check required commands
    local required_commands=("docker" "docker-compose" "curl" "jq")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            log_error "Required command '$cmd' not found"
            exit 1
        fi
    done
    
    # Check Docker daemon
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
    
    # Check if in correct directory
    if [[ ! -f "$PROJECT_ROOT/$COMPOSE_FILE" ]]; then
        log_error "Docker compose file not found: $PROJECT_ROOT/$COMPOSE_FILE"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

check_environment() {
    log "Checking environment configuration..."
    
    local env_file="$PROJECT_ROOT/.env.$ENVIRONMENT"
    if [[ ! -f "$env_file" ]]; then
        log_error "Environment file not found: $env_file"
        exit 1
    fi
    
    # Check required environment variables
    local required_vars=("GEMINI_API_KEY" "TELEGRAM_BOT_TOKEN" "POSTGRES_PASSWORD")
    for var in "${required_vars[@]}"; do
        if ! grep -q "^$var=" "$env_file" || grep -q "^$var=.*_here$" "$env_file"; then
            log_error "Required environment variable '$var' not set properly in $env_file"
            exit 1
        fi
    done
    
    log_success "Environment configuration check passed"
}

create_backup() {
    if [[ "$BACKUP_ENABLED" == "true" ]]; then
        log "Creating backup..."
        
        local backup_script="$DEPLOYMENT_DIR/scripts/backup.sh"
        if [[ -f "$backup_script" ]]; then
            bash "$backup_script" --auto
            log_success "Backup completed"
        else
            log_warning "Backup script not found, skipping backup"
        fi
    else
        log "Skipping backup (disabled)"
    fi
}

pull_images() {
    if [[ "$PULL_IMAGES" == "true" ]]; then
        log "Pulling latest images..."
        cd "$PROJECT_ROOT"
        docker-compose -f "$COMPOSE_FILE" pull
        log_success "Images pulled successfully"
    else
        log "Skipping image pull (disabled)"
    fi
}

deploy_application() {
    log "Deploying application..."
    
    cd "$PROJECT_ROOT"
    
    # Set environment
    export COMPOSE_PROJECT_NAME="legalrag-$ENVIRONMENT"
    
    # Deploy with zero-downtime strategy
    log "Starting deployment with zero-downtime strategy..."
    
    # Build new images if needed
    docker-compose -f "$COMPOSE_FILE" build
    
    # Deploy services one by one to minimize downtime
    log "Updating infrastructure services..."
    docker-compose -f "$COMPOSE_FILE" up -d postgres redis chromadb
    
    # Wait for infrastructure to be ready
    sleep 10
    
    log "Updating application services..."
    docker-compose -f "$COMPOSE_FILE" up -d legalrag-microservices legalrag-telegram-bot
    
    # Update reverse proxy last
    if docker-compose -f "$COMPOSE_FILE" config --services | grep -q nginx; then
        log "Updating reverse proxy..."
        docker-compose -f "$COMPOSE_FILE" up -d nginx
    fi
    
    log_success "Application deployed successfully"
}

rollback_deployment() {
    log "Rolling back to previous version..."
    
    cd "$PROJECT_ROOT"
    
    # Get previous version from backup
    local backup_dir="/opt/legalrag/backups"
    local latest_backup=$(ls -t "$backup_dir"/ | head -1)
    
    if [[ -n "$latest_backup" && -d "$backup_dir/$latest_backup" ]]; then
        log "Rolling back to backup: $latest_backup"
        
        # Stop current services
        docker-compose -f "$COMPOSE_FILE" down --timeout 30
        
        # Restore from backup (this would need to be implemented in backup script)
        bash "$DEPLOYMENT_DIR/scripts/backup.sh" --restore "$latest_backup"
        
        # Start services
        docker-compose -f "$COMPOSE_FILE" up -d
        
        log_success "Rollback completed"
    else
        log_error "No backup found for rollback"
        exit 1
    fi
}

run_health_checks() {
    if [[ "$HEALTH_CHECK" == "true" ]]; then
        log "Running health checks..."
        
        local health_script="$DEPLOYMENT_DIR/scripts/health-check.sh"
        if [[ -f "$health_script" ]]; then
            if bash "$health_script"; then
                log_success "All health checks passed"
            else
                log_error "Health checks failed"
                exit 1
            fi
        else
            log "Health check script not found, running basic checks..."
            
            # Basic health check
            local max_attempts=30
            local attempt=1
            
            while [[ $attempt -le $max_attempts ]]; do
                if curl -f -s http://localhost:8080/health > /dev/null; then
                    log_success "Application is responding to health checks"
                    break
                fi
                
                log "Waiting for application to be ready... (attempt $attempt/$max_attempts)"
                sleep 10
                attempt=$((attempt + 1))
            done
            
            if [[ $attempt -gt $max_attempts ]]; then
                log_error "Application failed to respond to health checks"
                exit 1
            fi
        fi
    else
        log "Skipping health checks (disabled)"
    fi
}

cleanup() {
    log "Cleaning up..."
    
    # Remove unused images and containers
    docker image prune -f
    docker container prune -f
    
    log_success "Cleanup completed"
}

# =============================================================================
# MAIN SCRIPT
# =============================================================================

main() {
    log "Starting LegalRAG deployment..."
    log "Environment: $ENVIRONMENT"
    log "Project root: $PROJECT_ROOT"
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --env)
                ENVIRONMENT="$2"
                shift 2
                ;;
            --backup)
                BACKUP_ENABLED="true"
                shift
                ;;
            --no-backup)
                BACKUP_ENABLED="false"
                shift
                ;;
            --no-pull)
                PULL_IMAGES="false"
                shift
                ;;
            --rollback)
                ROLLBACK_MODE="true"
                shift
                ;;
            --health-check)
                HEALTH_CHECK="true"
                shift
                ;;
            --no-health)
                HEALTH_CHECK="false"
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
    
    # Update compose file based on environment
    if [[ "$ENVIRONMENT" == "staging" ]]; then
        COMPOSE_FILE="docker-compose.staging.yml"
    fi
    
    # Run deployment
    if [[ "$ROLLBACK_MODE" == "true" ]]; then
        check_prerequisites
        rollback_deployment
        run_health_checks
    else
        check_prerequisites
        check_environment
        create_backup
        pull_images
        deploy_application
        run_health_checks
        cleanup
    fi
    
    log_success "Deployment completed successfully!"
    log "Application should be available at: http://localhost:8080"
}

# Trap errors and cleanup
trap 'log_error "Deployment failed at line $LINENO"' ERR

# Run main function
main "$@"