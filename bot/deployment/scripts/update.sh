#!/bin/bash
# =============================================================================
# LegalRAG - Quick Update Script
# =============================================================================
# 
# This script performs quick updates without full redeployment
# 
# Usage:
#   ./update.sh [service_name]
#
# Examples:
#   ./update.sh                    # Update all services
#   ./update.sh legalrag-microservices # Update only microservices
#   ./update.sh legalrag-telegram-bot  # Update only telegram bot
#
# =============================================================================

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

COMPOSE_FILE="docker-compose.prod.yml"
SERVICE_NAME="${1:-}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# =============================================================================
# FUNCTIONS
# =============================================================================

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✅ $1${NC}"
}

log_error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ❌ $1${NC}"
}

check_service_health() {
    local service="$1"
    local max_attempts=20
    local attempt=1
    
    log "Checking health of $service..."
    
    while [[ $attempt -le $max_attempts ]]; do
        if docker-compose -f "$COMPOSE_FILE" ps "$service" | grep -q "Up (healthy)"; then
            log_success "$service is healthy"
            return 0
        fi
        
        sleep 3
        attempt=$((attempt + 1))
    done
    
    log_error "$service health check failed"
    return 1
}

update_service() {
    local service="$1"
    
    log "Updating service: $service"
    
    # Check if service exists
    if ! docker-compose -f "$COMPOSE_FILE" config --services | grep -q "^$service$"; then
        log_error "Service '$service' not found"
        exit 1
    fi
    
    cd "$PROJECT_ROOT"
    
    # Build and update the service
    log "Building $service..."
    docker-compose -f "$COMPOSE_FILE" build "$service"
    
    log "Updating $service with zero downtime..."
    docker-compose -f "$COMPOSE_FILE" up -d --no-deps "$service"
    
    # Check health
    if check_service_health "$service"; then
        log_success "Service $service updated successfully"
    else
        log_error "Service $service update failed"
        exit 1
    fi
}

update_all_services() {
    log "Updating all application services..."
    
    cd "$PROJECT_ROOT"
    
    # Get list of application services (exclude infrastructure)
    local services=($(docker-compose -f "$COMPOSE_FILE" config --services | grep -E "legalrag-|nginx"))
    
    for service in "${services[@]}"; do
        update_service "$service"
    done
}

show_status() {
    log "Current service status:"
    cd "$PROJECT_ROOT"
    docker-compose -f "$COMPOSE_FILE" ps
}

# =============================================================================
# MAIN SCRIPT
# =============================================================================

main() {
    log "Starting LegalRAG update..."
    
    if [[ -n "$SERVICE_NAME" ]]; then
        update_service "$SERVICE_NAME"
    else
        update_all_services
    fi
    
    show_status
    
    log_success "Update completed successfully!"
}

# Run main function
main "$@"