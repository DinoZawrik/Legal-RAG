#!/bin/bash
# =============================================================================
# Alpha AI Assistant - Quick Restore Script
# =============================================================================
# 
# Wrapper script for quick restore operations
# 
# Usage:
#   ./restore.sh [backup_name]
#
# Examples:
#   ./restore.sh                           # Interactive restore (shows list)
#   ./restore.sh backup-2024-01-15-12-30   # Restore specific backup
#
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_SCRIPT="$SCRIPT_DIR/backup.sh"

# Colors
BLUE='\033[0;34m'
GREEN='\033[0;32m'
NC='\033[0m'

log() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✅ $1${NC}"
}

if [[ $# -eq 0 ]]; then
    # Interactive mode
    log "Alpha AI Assistant - Interactive Restore"
    echo
    
    # Show available backups
    bash "$BACKUP_SCRIPT" --list
    echo
    
    read -p "Enter backup name to restore (or press Enter to cancel): " backup_name
    
    if [[ -z "$backup_name" ]]; then
        log "Restore cancelled"
        exit 0
    fi
    
    # Execute restore
    bash "$BACKUP_SCRIPT" --restore "$backup_name"
else
    # Direct restore
    backup_name="$1"
    log "Restoring backup: $backup_name"
    bash "$BACKUP_SCRIPT" --restore "$backup_name"
fi

log_success "Restore operation completed!"