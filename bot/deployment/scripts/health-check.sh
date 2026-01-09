#!/bin/bash
# =============================================================================
# LegalRAG - Health Check Script
# =============================================================================
# 
# This script performs comprehensive health checks on all system components
# 
# Usage:
#   ./health-check.sh [options]
#
# Options:
#   --verbose        Enable verbose output
#   --json          Output results in JSON format
#   --check SERVICE  Check specific service only
#   --timeout SEC   Set timeout for checks (default: 30)
#   --help          Show this help message
#
# Exit codes:
#   0 - All checks passed
#   1 - Some checks failed
#   2 - Critical checks failed
#
# =============================================================================

set -euo pipefail

# =============================================================================
# CONFIGURATION
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

COMPOSE_FILE="docker-compose.prod.yml"
VERBOSE="false"
JSON_OUTPUT="false"
SPECIFIC_SERVICE=""
TIMEOUT="30"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Health check results
declare -A HEALTH_RESULTS

# =============================================================================
# FUNCTIONS
# =============================================================================

log() {
    if [[ "$VERBOSE" == "true" || "$JSON_OUTPUT" == "false" ]]; then
        echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
    fi
}

log_success() {
    if [[ "$JSON_OUTPUT" == "false" ]]; then
        echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] ✅ $1${NC}"
    fi
}

log_warning() {
    if [[ "$JSON_OUTPUT" == "false" ]]; then
        echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] ⚠️  $1${NC}"
    fi
}

log_error() {
    if [[ "$JSON_OUTPUT" == "false" ]]; then
        echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ❌ $1${NC}"
    fi
}

show_help() {
    cat << EOF
LegalRAG - Health Check Script

Usage: $0 [options]

Options:
    --verbose        Enable verbose output
    --json          Output results in JSON format
    --check SERVICE Check specific service only
    --timeout SEC   Set timeout for checks (default: 30)
    --help          Show this help message

Examples:
    $0                          # Run all health checks
    $0 --verbose               # Run with verbose output
    $0 --check postgres        # Check only PostgreSQL
    $0 --json                  # Output results in JSON format

EOF
}

# =============================================================================
# HEALTH CHECK FUNCTIONS
# =============================================================================

check_docker() {
    log "Checking Docker daemon..."
    
    if docker info &> /dev/null; then
        HEALTH_RESULTS["docker"]="healthy"
        log_success "Docker daemon is running"
        return 0
    else
        HEALTH_RESULTS["docker"]="unhealthy"
        log_error "Docker daemon is not running"
        return 1
    fi
}

check_docker_compose() {
    log "Checking Docker Compose..."
    
    cd "$PROJECT_ROOT"
    
    if docker-compose -f "$COMPOSE_FILE" config &> /dev/null; then
        HEALTH_RESULTS["docker-compose"]="healthy"
        log_success "Docker Compose configuration is valid"
        return 0
    else
        HEALTH_RESULTS["docker-compose"]="unhealthy"
        log_error "Docker Compose configuration is invalid"
        return 1
    fi
}

check_service_running() {
    local service="$1"
    log "Checking if $service is running..."
    
    cd "$PROJECT_ROOT"
    
    if docker-compose -f "$COMPOSE_FILE" ps "$service" | grep -q "Up"; then
        HEALTH_RESULTS["${service}-running"]="healthy"
        if [[ "$VERBOSE" == "true" ]]; then
            log_success "$service is running"
        fi
        return 0
    else
        HEALTH_RESULTS["${service}-running"]="unhealthy"
        log_error "$service is not running"
        return 1
    fi
}

check_postgres_health() {
    log "Checking PostgreSQL health..."
    
    local max_attempts=$((TIMEOUT / 2))
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if docker exec legalrag_postgres_prod pg_isready -U legalrag_user -d legalrag_db &> /dev/null; then
            HEALTH_RESULTS["postgres-health"]="healthy"
            log_success "PostgreSQL is healthy"
            return 0
        fi
        
        if [[ "$VERBOSE" == "true" ]]; then
            log "PostgreSQL not ready, attempt $attempt/$max_attempts"
        fi
        
        sleep 2
        attempt=$((attempt + 1))
    done
    
    HEALTH_RESULTS["postgres-health"]="unhealthy"
    log_error "PostgreSQL health check failed"
    return 1
}

check_redis_health() {
    log "Checking Redis health..."
    
    local max_attempts=$((TIMEOUT / 2))
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if docker exec legalrag_redis_prod redis-cli ping 2>/dev/null | grep -q "PONG"; then
            HEALTH_RESULTS["redis-health"]="healthy"
            log_success "Redis is healthy"
            return 0
        fi
        
        if [[ "$VERBOSE" == "true" ]]; then
            log "Redis not ready, attempt $attempt/$max_attempts"
        fi
        
        sleep 2
        attempt=$((attempt + 1))
    done
    
    HEALTH_RESULTS["redis-health"]="unhealthy"
    log_error "Redis health check failed"
    return 1
}

check_chromadb_health() {
    log "Checking ChromaDB health..."
    
    local max_attempts=$((TIMEOUT / 2))
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -f -s http://localhost:8000/api/v1/heartbeat &> /dev/null; then
            HEALTH_RESULTS["chromadb-health"]="healthy"
            log_success "ChromaDB is healthy"
            return 0
        fi
        
        if [[ "$VERBOSE" == "true" ]]; then
            log "ChromaDB not ready, attempt $attempt/$max_attempts"
        fi
        
        sleep 2
        attempt=$((attempt + 1))
    done
    
    HEALTH_RESULTS["chromadb-health"]="unhealthy"
    log_error "ChromaDB health check failed"
    return 1
}

check_microservices_health() {
    log "Checking LegalRAG Microservices health..."
    
    local max_attempts=$((TIMEOUT / 2))
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -f -s http://localhost:8080/health &> /dev/null; then
            HEALTH_RESULTS["microservices-health"]="healthy"
            log_success "LegalRAG Microservices are healthy"
            return 0
        fi
        
        if [[ "$VERBOSE" == "true" ]]; then
            log "Microservices not ready, attempt $attempt/$max_attempts"
        fi
        
        sleep 2
        attempt=$((attempt + 1))
    done
    
    HEALTH_RESULTS["microservices-health"]="unhealthy"
    log_error "LegalRAG Microservices health check failed"
    return 1
}

check_api_functionality() {
    log "Checking API functionality..."
    
    # Test health endpoint with detailed response
    local health_response
    if health_response=$(curl -s -w "%{http_code}" http://localhost:8080/health 2>/dev/null); then
        local http_code="${health_response: -3}"
        local response_body="${health_response%???}"
        
        if [[ "$http_code" == "200" ]]; then
            HEALTH_RESULTS["api-functionality"]="healthy"
            log_success "API functionality check passed"
            
            if [[ "$VERBOSE" == "true" && -n "$response_body" ]]; then
                log "API Response: $response_body"
            fi
            return 0
        else
            HEALTH_RESULTS["api-functionality"]="unhealthy"
            log_error "API returned HTTP $http_code"
            return 1
        fi
    else
        HEALTH_RESULTS["api-functionality"]="unhealthy"
        log_error "API functionality check failed"
        return 1
    fi
}

check_system_resources() {
    log "Checking system resources..."
    
    local issues=0
    
    # Check disk space
    local disk_usage
    disk_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    
    if [[ $disk_usage -gt 90 ]]; then
        log_error "Disk usage is critical: ${disk_usage}%"
        issues=$((issues + 1))
    elif [[ $disk_usage -gt 80 ]]; then
        log_warning "Disk usage is high: ${disk_usage}%"
    fi
    
    # Check memory usage
    local memory_usage
    memory_usage=$(free | grep Mem | awk '{printf("%.0f", $3/$2 * 100.0)}')
    
    if [[ $memory_usage -gt 90 ]]; then
        log_error "Memory usage is critical: ${memory_usage}%"
        issues=$((issues + 1))
    elif [[ $memory_usage -gt 80 ]]; then
        log_warning "Memory usage is high: ${memory_usage}%"
    fi
    
    # Check load average
    local load_avg
    load_avg=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
    local cpu_cores
    cpu_cores=$(nproc)
    
    if (( $(echo "$load_avg > $cpu_cores * 2" | bc -l) )); then
        log_error "Load average is critical: $load_avg (CPUs: $cpu_cores)"
        issues=$((issues + 1))
    fi
    
    if [[ $issues -eq 0 ]]; then
        HEALTH_RESULTS["system-resources"]="healthy"
        log_success "System resources are healthy"
        return 0
    else
        HEALTH_RESULTS["system-resources"]="unhealthy"
        log_error "System resources have issues"
        return 1
    fi
}

check_logs_for_errors() {
    log "Checking logs for recent errors..."
    
    local error_count=0
    
    # Check Docker compose logs for errors in the last 10 minutes
    cd "$PROJECT_ROOT"
    local recent_errors
    recent_errors=$(docker-compose -f "$COMPOSE_FILE" logs --since="10m" 2>&1 | grep -iE "error|exception|failed|critical" | wc -l)
    
    if [[ $recent_errors -gt 10 ]]; then
        HEALTH_RESULTS["logs-errors"]="unhealthy"
        log_error "Found $recent_errors error entries in recent logs"
        return 1
    elif [[ $recent_errors -gt 5 ]]; then
        HEALTH_RESULTS["logs-errors"]="warning"
        log_warning "Found $recent_errors error entries in recent logs"
        return 0
    else
        HEALTH_RESULTS["logs-errors"]="healthy"
        log_success "No critical errors found in recent logs"
        return 0
    fi
}

# =============================================================================
# OUTPUT FUNCTIONS
# =============================================================================

output_json_results() {
    local overall_status="healthy"
    local critical_failures=0
    local warnings=0
    
    # Determine overall status
    for service in "${!HEALTH_RESULTS[@]}"; do
        case "${HEALTH_RESULTS[$service]}" in
            "unhealthy")
                critical_failures=$((critical_failures + 1))
                overall_status="unhealthy"
                ;;
            "warning")
                warnings=$((warnings + 1))
                if [[ "$overall_status" == "healthy" ]]; then
                    overall_status="warning"
                fi
                ;;
        esac
    done
    
    # Output JSON
    echo "{"
    echo "  \"timestamp\": \"$(date -Iseconds)\","
    echo "  \"overall_status\": \"$overall_status\","
    echo "  \"summary\": {"
    echo "    \"total_checks\": ${#HEALTH_RESULTS[@]},"
    echo "    \"healthy\": $(echo "${HEALTH_RESULTS[@]}" | grep -o "healthy" | wc -l),"
    echo "    \"warnings\": $warnings,"
    echo "    \"failures\": $critical_failures"
    echo "  },"
    echo "  \"checks\": {"
    
    local first=true
    for service in $(printf '%s\n' "${!HEALTH_RESULTS[@]}" | sort); do
        if [[ "$first" == "false" ]]; then
            echo ","
        fi
        echo -n "    \"$service\": \"${HEALTH_RESULTS[$service]}\""
        first=false
    done
    
    echo ""
    echo "  }"
    echo "}"
}

# =============================================================================
# MAIN SCRIPT
# =============================================================================

run_health_checks() {
    local failed_checks=0
    local critical_failed_checks=0
    
    if [[ -n "$SPECIFIC_SERVICE" ]]; then
        # Run specific service check
        case "$SPECIFIC_SERVICE" in
            "docker")
                check_docker || failed_checks=$((failed_checks + 1))
                ;;
            "postgres")
                check_service_running "postgres" || critical_failed_checks=$((critical_failed_checks + 1))
                check_postgres_health || failed_checks=$((failed_checks + 1))
                ;;
            "redis")
                check_service_running "redis" || critical_failed_checks=$((critical_failed_checks + 1))
                check_redis_health || failed_checks=$((failed_checks + 1))
                ;;
            "chromadb")
                check_service_running "chromadb" || critical_failed_checks=$((critical_failed_checks + 1))
                check_chromadb_health || failed_checks=$((failed_checks + 1))
                ;;
            "microservices")
                check_service_running "legalrag-microservices" || critical_failed_checks=$((critical_failed_checks + 1))
                check_microservices_health || failed_checks=$((failed_checks + 1))
                ;;
            *)
                log_error "Unknown service: $SPECIFIC_SERVICE"
                exit 1
                ;;
        esac
    else
        # Run all checks
        log "Running comprehensive health checks..."
        
        # Critical infrastructure checks
        check_docker || critical_failed_checks=$((critical_failed_checks + 1))
        check_docker_compose || critical_failed_checks=$((critical_failed_checks + 1))
        
        # Service running checks
        check_service_running "postgres" || critical_failed_checks=$((critical_failed_checks + 1))
        check_service_running "redis" || critical_failed_checks=$((critical_failed_checks + 1))
        check_service_running "chromadb" || critical_failed_checks=$((critical_failed_checks + 1))
        check_service_running "legalrag-microservices" || critical_failed_checks=$((critical_failed_checks + 1))
        
        # Service health checks
        check_postgres_health || failed_checks=$((failed_checks + 1))
        check_redis_health || failed_checks=$((failed_checks + 1))
        check_chromadb_health || failed_checks=$((failed_checks + 1))
        check_microservices_health || failed_checks=$((failed_checks + 1))
        
        # Functionality checks
        check_api_functionality || failed_checks=$((failed_checks + 1))
        
        # System checks
        check_system_resources || failed_checks=$((failed_checks + 1))
        check_logs_for_errors || failed_checks=$((failed_checks + 1))
    fi
    
    # Output results
    if [[ "$JSON_OUTPUT" == "true" ]]; then
        output_json_results
    else
        log ""
        log "Health check summary:"
        log "  Total checks: ${#HEALTH_RESULTS[@]}"
        log "  Healthy: $(echo "${HEALTH_RESULTS[@]}" | grep -o "healthy" | wc -l)"
        log "  Warnings: $(echo "${HEALTH_RESULTS[@]}" | grep -o "warning" | wc -l)"
        log "  Failures: $(echo "${HEALTH_RESULTS[@]}" | grep -o "unhealthy" | wc -l)"
    fi
    
    # Determine exit code
    if [[ $critical_failed_checks -gt 0 ]]; then
        if [[ "$JSON_OUTPUT" == "false" ]]; then
            log_error "Critical health checks failed!"
        fi
        exit 2
    elif [[ $failed_checks -gt 0 ]]; then
        if [[ "$JSON_OUTPUT" == "false" ]]; then
            log_warning "Some health checks failed"
        fi
        exit 1
    else
        if [[ "$JSON_OUTPUT" == "false" ]]; then
            log_success "All health checks passed!"
        fi
        exit 0
    fi
}

main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --verbose)
                VERBOSE="true"
                shift
                ;;
            --json)
                JSON_OUTPUT="true"
                shift
                ;;
            --check)
                SPECIFIC_SERVICE="$2"
                shift 2
                ;;
            --timeout)
                TIMEOUT="$2"
                shift 2
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
    
    run_health_checks
}

# Run main function
main "$@"