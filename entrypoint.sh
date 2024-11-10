#!/usr/bin/env bash

# Exit on error, undefined variables, and pipe failures
set -euo pipefail
IFS=$'\n\t'

# Configuration
readonly CACHE_DIR="/app/.cache"
readonly LOG_DIR="/app/logs"
readonly BACKUP_DIR="/app/backups"

readonly ENV_FILE="/app/.env"
readonly CERT_DIR="/app/config/certs"
readonly CERT_FILES=(
    "${CERT_DIR}/verdure.cert.pem"
    "${CERT_DIR}/verdure.private.key"
    "${CERT_DIR}/root-CA.crt"
)

readonly ARDUINO_SKETCH_DIR="/app/hardware"
readonly ARDUINO_FQBN="arduino:avr:uno"
readonly ARDUINO_DEFAULT_PORT="/dev/ttyUSB0"

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m'

# Logging functions
log() {
    local level=$1
    shift
    echo -e "[$(date +'%Y-%m-%d %H:%M:%S')] ${level}: $*" | tee -a "/app/logs/entrypoint.log"
}
log_info() { log "${GREEN}INFO${NC}" "$*"; }
log_warn() { log "${YELLOW}WARN${NC}" "$*" >&2; }
log_error() { log "${RED}ERROR${NC}" "$*" >&2; }

command_exists() {
    command -v "$1" &> /dev/null
}

# Version comparison utility
version_gt() {
    test "$(printf '%s\n' "$@" | sort -V | head -n 1)" != "$1"
}

# Initialize working directories
init_directories() {
    mkdir -p "$CACHE_DIR" "$LOG_DIR" "$BACKUP_DIR"
    chmod 700 "$CACHE_DIR" "$LOG_DIR" "$BACKUP_DIR"
    log_info "Initialized directories."
}

# Validate environment
check_environment() {
    if [ ! -f "$ENV_FILE" ]; then
        log_error "Environment file ($ENV_FILE) is missing."
        exit 1
    fi

    # Verify all required certificates exist
    local missing_certs=()
    for cert_file in "${CERT_FILES[@]}"; do
        if [ ! -f "$cert_file" ]; then
            missing_certs+=("$cert_file")
        fi
    done

    if [ ${#missing_certs[@]} -ne 0 ]; then
        log_error "Missing certificate files:"
        printf '%s\n' "${missing_certs[@]}"
        exit 1
    fi
    log_info "Environment and certificates validated."
}

# Backup certificates
backup_certificates() {
    local backup_timestamp
    backup_timestamp=$(date +%Y%m%d_%H%M%S)
    local backup_path="${BACKUP_DIR}/certs_${backup_timestamp}"

    mkdir -p "$backup_path"
    for cert_file in "${CERT_FILES[@]}"; do
        if [ -f "$cert_file" ]; then
            cp "$cert_file" "$backup_path/"
        fi
    done
    log_info "Certificates backed up to $backup_path."
}

# Setup Arduino CLI and flash board
setup_arduino() {
    log_info "Setting up Arduino CLI..."

    if command_exists arduino-cli; then
        log_info "Arduino CLI is already installed."
    else
        log_error "Arduino CLI is not installed inside the container."
        exit 1
    fi

    # Retry mechanism for updating Arduino CLI index
    local retry_count=3
    for ((i=1;i<=retry_count;i++)); do
        if arduino-cli core update-index; then
            log_info "Arduino CLI index updated successfully."
            break
        else
            log_warn "Failed to update Arduino CLI index. Attempt $i/$retry_count."
            sleep 2
        fi
        if [ $i -eq $retry_count ]; then
            log_error "Failed to update Arduino CLI index after $retry_count attempts."
            exit 1
        fi
    done

    log_info "Installing Arduino AVR core..."
    arduino-cli core install arduino:avr || { log_error "Failed to install Arduino AVR core."; exit 1; }

    # Install DHT and Adafruit libraries
    log_info "Installing required libraries..."
    arduino-cli lib install "DHT Sensor Library@1.4.6" || { log_error "Failed to install DHT11 Arduino Library."; exit 1; }
    arduino-cli lib install "Adafruit Unified Sensor@1.1.14" || { log_error "Failed to install Adafruit Unified Sensor library."; exit 1; }

    # Detect Arduino board port
    local port
    port=$(arduino-cli board list | grep -E "ttyUSB|ttyACM|cu\.usbmodem" | awk '{print $1}')

    if [ -z "$port" ]; then
        port="${ARDUINO_DEFAULT_PORT}"
        log_warn "No Arduino board detected, using default port: $port"
    else
        log_info "Arduino board detected on port: $port"
    fi

    # Save the detected port as an environment variable
    export SERIAL_PORT="$port"
    log_info "Detected serial port: $SERIAL_PORT"

    # Compile and upload Arduino sketch
    log_info "Compiling Arduino sketch..."
    arduino-cli compile --fqbn "$ARDUINO_FQBN" "$ARDUINO_SKETCH_DIR" || { log_error "Compilation failed."; exit 1; }

    log_info "Uploading to Arduino..."
    arduino-cli upload -p "$port" --fqbn "$ARDUINO_FQBN" "$ARDUINO_SKETCH_DIR" || { log_error "Upload failed."; exit 1; }

    log_info "Arduino setup completed."
}

# Manage cache
manage_cache() {
    local cache_size
    cache_size=$(du -sh "$CACHE_DIR" | cut -f1)
    log_info "Current cache size: $cache_size"

    # Clean old cache files (>7 days)
    find "$CACHE_DIR" -type f -mtime +7 -delete
    log_info "Old cache files cleaned."
}

# Main initialization
main() {
    init_directories
    check_environment
    backup_certificates
    setup_arduino
    manage_cache

    # Execute the main container command
    exec "$@"
}

main "$@"
