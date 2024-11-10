#!/usr/bin/env bash

# Exit on error, undefined variables, and pipe failures
set -euo pipefail
IFS=$'\n\t'

# Configuration
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly CACHE_DIR="${SCRIPT_DIR}/.cache"
readonly LOG_DIR="${SCRIPT_DIR}/logs"
readonly BACKUP_DIR="${SCRIPT_DIR}/backups"

# Version requirements
readonly DOCKER_MIN_VERSION="20.10.0"
readonly DOCKER_COMPOSE_MIN_VERSION="1.2.9"
readonly ARDUINO_CLI_MIN_VERSION="0.34.2"

readonly VENV_DIR="venv"
readonly PYTHON_MIN_VERSION="3.10"
readonly REQUIREMENTS_FILE="requirements.txt"
readonly ENV_FILE=".env"
readonly CERT_DIR="config/certs"
readonly CERT_FILES=(
    "${CERT_DIR}/verdure.cert.pem"
    "${CERT_DIR}/verdure.private.key"
    "${CERT_DIR}/root-CA.crt"
)

readonly DOCKER_COMPOSE_FILE="docker-compose.yml"
readonly DOCKER_IMAGE_NAME="verdure-app"

readonly ARDUINO_SKETCH_DIR="hardware"
readonly ARDUINO_FQBN="arduino:avr:uno"
readonly ARDUINO_DEFAULT_PORT="${DEFAULT_SERIAL_PORT:-/dev/ttyUSB0}"
readonly ARDUINO_CLI_VERSION="0.34.2"

readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m'

# Enhanced logging with timestamps
log() {
    local level=$1
    shift
    echo -e "[$(date +'%Y-%m-%d %H:%M:%S')] ${level}: $*" | tee -a "${LOG_DIR}/run.log"
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
}

# Validate tool versions
check_tool_versions() {
    # Docker version check
    if command_exists docker; then
        local docker_version
        docker_version=$(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n1)
        if version_gt "$DOCKER_MIN_VERSION" "$docker_version"; then
            log_error "Docker version $DOCKER_MIN_VERSION or higher required (found $docker_version)"
            exit 1
        fi
    fi

    # Docker Compose version check
    if command_exists docker-compose; then
        local compose_version
        compose_version=$(docker-compose --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -n1)
        if version_gt "$DOCKER_COMPOSE_MIN_VERSION" "$compose_version"; then
            log_error "Docker Compose version $DOCKER_COMPOSE_MIN_VERSION or higher required (found $compose_version)"
            exit 1
        fi
    fi
}

# verify Python version meets minimum requirement
check_python_version() {
    local python_version
    python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    
    if ! command_exists python3; then
        log_error "Python 3 is required but not installed."
        exit 1
    fi
    
    if ! awk -v ver="$python_version" -v req="$PYTHON_MIN_VERSION" 'BEGIN {exit (ver < req)}'; then
        log_error "Python ${PYTHON_MIN_VERSION} or higher is required (found ${python_version})"
        exit 1
    fi
}

# verify all dependencies are installed
check_dependencies() {
    local missing_deps=()

    if ! command_exists pip3; then
        missing_deps+=("pip3")
    fi

    if ! command_exists virtualenv; then
        log_warn "virtualenv not found, installing..."
        pip3 install virtualenv
    fi

    if [ ${#missing_deps[@]} -ne 0 ]; then
        log_error "Missing required dependencies: ${missing_deps[*]}"
        exit 1
    fi
}

setup_virtualenv() {
    if [ ! -d "$VENV_DIR" ]; then
        log_info "Creating virtual environment..."
        virtualenv "$VENV_DIR"
    fi

    log_info "Activating virtual environment..."
    # shellcheck disable=SC1091
    source "${VENV_DIR}/bin/activate"
}

# Enhanced dependency installation with parallel processing
install_dependencies() {
    if [ ! -f "$REQUIREMENTS_FILE" ]; then
        log_error "Requirements file ($REQUIREMENTS_FILE) is missing."
        exit 1
    fi

    log_info "Installing dependencies in parallel..."
    # Split requirements into chunks for parallel installation
    local temp_dir
    temp_dir=$(mktemp -d)
    split -l 10 "$REQUIREMENTS_FILE" "${temp_dir}/requirements-"
    
    # Install chunks in parallel
    for chunk in "${temp_dir}"/requirements-*; do
        pip3 install -r "$chunk" &
    done
    wait

    rm -rf "$temp_dir"
}

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
}

# Certificate management
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
    log_info "Certificates backed up to $backup_path"
}

run_application() {
    log_info "Starting the application..."
    python3 app.py
}

check_docker() {
    if ! command_exists docker; then
        log_error "Docker is not installed"
        exit 1
    fi

    if ! docker info >/dev/null 2>&1; then
        log_error "Docker daemon is not running"
        exit 1
    fi

    if ! command_exists docker-compose; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
}

# build and run docker containers
run_docker() {
    local serial_port="$1"

    log_info "Building and starting Docker containers..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" up --build -d

    # Pass the serial port to the container
    docker-compose -f "$DOCKER_COMPOSE_FILE" exec app bash -c "export SERIAL_PORT=$serial_port"

    log_info "Container logs (press Ctrl+C to exit):"
    docker-compose -f "$DOCKER_COMPOSE_FILE" logs -f
}

stop_docker() {
    log_info "Stopping Docker containers..."
    docker-compose -f "$DOCKER_COMPOSE_FILE" down

    if docker network inspect hydroponics_default >/dev/null 2>&1; then
        log_info "Removing network hydroponics_default..."
        docker network rm hydroponics_default
    else
        log_warn "Network hydroponics_default not found."
    fi
}

cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Script failed with exit code: $exit_code"
        stop_docker
    fi
    exit $exit_code
}

# setup Arduino CLI and flash board
setup_arduino() {
    log_info "Setting up Arduino CLI..."

    # determine the installation directory dynamically
    INSTALL_DIR="${INSTALL_DIR:-$HOME/.arduino-cli}"

    # add the installation directory to PATH
    export PATH="$INSTALL_DIR:$PATH"

    # ensure the installation directory exists
    if [ ! -d "$INSTALL_DIR" ]; then
        log_info "Creating installation directory at $INSTALL_DIR..."
        mkdir -p "$INSTALL_DIR" || { log_error "Failed to create installation directory."; exit 1; }
    fi

    # check if Arduino CLI is already installed
    if command_exists arduino-cli; then
        log_info "Arduino CLI is already installed."
    else
        OS=$(uname | tr '[:upper:]' '[:lower:]')
        ARCH=$(uname -m)

        case "$ARCH" in
            x86_64)
                ARCH="64bit"
                ;;
            aarch64 | arm64)
                ARCH="ARM64"
                ;;
            armv7l | armv6l)
                ARCH="ARMv7"
                ;;
            *)
                log_error "Unsupported architecture: $ARCH"
                exit 1
                ;;
        esac

        case "$OS" in
            linux)
                OS="Linux"
                ;;
            darwin)
                OS="macOS"
                ;;
            windows)
                OS="Windows"
                ;;
            *)
                log_error "Unsupported operating system: $OS"
                exit 1
                ;;
        esac

        RELEASE_VERSION="v1.Z"
        BASE_URL="https://github.com/arduino/arduino-cli/releases/download/${RELEASE_VERSION}"
        
        if [ "$OS" = "Windows" ]; then
            FILE_EXT="zip"
        else
            FILE_EXT="tar.gz"
        fi

        DOWNLOAD_URL="${BASE_URL}/arduino-cli_1.0.4_${OS}_${ARCH}.${FILE_EXT}"

        log_info "Downloading Arduino CLI from $DOWNLOAD_URL..."

        TEMP_DIR=$(mktemp -d)
        TAR_FILE="${TEMP_DIR}/arduino-cli.${FILE_EXT}"

        curl -L -o "$TAR_FILE" "$DOWNLOAD_URL"
        if [ $? -ne 0 ]; then
            log_error "Failed to download Arduino CLI from $DOWNLOAD_URL"
            exit 1
        fi

        log_info "Extracting Arduino CLI..."
        if [ "$OS" = "Windows" ]; then
            unzip "$TAR_FILE" -d "$TEMP_DIR" || { log_error "Failed to unzip Arduino CLI archive."; exit 1; }
            cp "${TEMP_DIR}/arduino-cli.exe" "$INSTALL_DIR/" || { log_error "Failed to copy arduino-cli.exe to $INSTALL_DIR."; exit 1; }
        else
            tar -xzf "$TAR_FILE" -C "$TEMP_DIR" || { log_error "Failed to extract Arduino CLI archive."; exit 1; }
            cp "${TEMP_DIR}/arduino-cli" "$INSTALL_DIR/" || { log_error "Failed to copy arduino-cli to $INSTALL_DIR."; exit 1; }
            chmod +x "$INSTALL_DIR/arduino-cli"
        fi

        rm -rf "$TEMP_DIR"

        if ! command_exists arduino-cli; then
            log_error "arduino-cli installation failed."
            exit 1
        fi

        log_info "Arduino CLI installed successfully at $INSTALL_DIR."
    fi

    log_info "Updating Arduino CLI index..."
    arduino-cli core update-index || { log_error "Failed to update Arduino CLI index."; exit 1; }

    log_info "Installing Arduino AVR core..."
    arduino-cli core install arduino:avr || { log_error "Failed to install Arduino AVR core."; exit 1; }

    # install DHT and Adafruit libraries
    log_info "Installing required libraries..."
    arduino-cli lib install "DHT Sensor Library@1.4.6" || { log_error "Failed to install DHT11 Arduino Library."; exit 1; }
    arduino-cli lib install "Adafruit Unified Sensor@1.1.14" || { log_error "Failed to install Adafruit Unified Sensor library."; exit 1; }

    # detect arduino board port
    local port
    port=$(arduino-cli board list | grep -E "ttyUSB|ttyACM|cu\.usbmodem" | awk '{print $1}')

    if [ -z "$port" ]; then
        port="${ARDUINO_DEFAULT_PORT:-/dev/ttyUSB0}"
        log_warn "No Arduino board detected, using default port: $port"
    else
        log_info "Arduino board detected on port: $port"
    fi

    # Save the detected port to a temporary file
    echo "$port" > /tmp/arduino_port

    log_info "Compiling Arduino sketch..."
    arduino-cli compile --fqbn "$ARDUINO_FQBN" "$ARDUINO_SKETCH_DIR" || { log_error "Compilation failed."; exit 1; }

    log_info "Uploading to Arduino..."
    arduino-cli upload -p "$port" --fqbn "$ARDUINO_FQBN" "$ARDUINO_SKETCH_DIR" || { log_error "Upload failed."; exit 1; }
}

# Enhanced Arduino port detection
detect_arduino_port() {
    local ports=()
    local preferred_ports=("ttyUSB" "ttyACM" "cu.usbmodem")
    
    for prefix in "${preferred_ports[@]}"; do
        while read -r port; do
            if [[ $port == *"$prefix"* ]]; then
                ports+=("$port")
            fi
        done < <(ls /dev/$prefix* 2>/dev/null || true)
    done

    if [ ${#ports[@]} -eq 0 ]; then
        echo "${ARDUINO_DEFAULT_PORT}"
        return
    fi

    # Verify port accessibility
    for port in "${ports[@]}"; do
        if [ -w "$port" ]; then
            echo "$port"
            return
        fi
    done

    echo "${ARDUINO_DEFAULT_PORT}"
}

# Docker health check
check_docker_health() {
    local container_name=$1
    local max_attempts=30
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        if docker inspect "$container_name" --format '{{.State.Health.Status}}' 2>/dev/null | grep -q "healthy"; then
            return 0
        fi
        log_info "Waiting for container $container_name to be healthy (attempt $attempt/$max_attempts)..."
        sleep 2
        ((attempt++))
    done

    log_error "Container $container_name failed to become healthy"
    return 1
}

# Cache management
manage_cache() {
    local cache_size
    cache_size=$(du -sh "$CACHE_DIR" | cut -f1)
    log_info "Current cache size: $cache_size"

    # Clean old cache files (>7 days)
    find "$CACHE_DIR" -type f -mtime +7 -delete
}

main() {
    trap cleanup EXIT
    init_directories
    
    # Validate environment
    check_tool_versions
    check_environment
    
    # Backup certificates
    backup_certificates
    
    # Setup Arduino
    setup_arduino
    
    # Read the detected serial port
    local detected_port
    detected_port=$(detect_arduino_port)
    
    # Cache management
    manage_cache
    
    # Main execution logic
    if [[ "${1:-}" == "--docker" ]]; then
        check_docker
        run_docker "$detected_port"
        check_docker_health "$DOCKER_IMAGE_NAME"
    else
        check_python_version
        check_dependencies
        setup_virtualenv
        install_dependencies
        run_application
    fi
}

main "$@"