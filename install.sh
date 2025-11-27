#!/usr/bin/env bash
set -euo pipefail

APP_GIT_URL="https://github.com/avadec/avst-service.git"
DEFAULT_INSTALL_DIR="/opt/avst-service"
DEFAULT_AUDIO_PATH="/mnt/audio"
DEFAULT_API_PORT="8000"
ENV_FILE_NAME=".env.avst"

INSTALL_MODE="prod"               # "prod" or "testing"
COMPOSE_FILE_NAME="docker-compose.yml"

COMPOSE_FILES="-f docker-compose.yml"

# ---------- helpers ----------

log() {
  echo -e "[avst-install] $*"
}

fatal() {
  echo -e "[avst-install] ERROR: $*" >&2
  exit 1
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

ask_yes_no() {
  local prompt="$1"
  local default="${2:-y}"
  local reply

  local default_hint
  if [[ "$default" =~ ^[Yy]$ ]]; then
    default_hint="Y/n"
  else
    default_hint="y/N"
  fi

  while true; do
    read -rp "$prompt [$default_hint] " reply || true
    reply="${reply:-$default}"

    # normalize to lowercase in a Bash 3–compatible way
    local reply_lc
    reply_lc="$(printf '%s' "$reply" | tr '[:upper:]' '[:lower:]')"

    case "$reply_lc" in
      y|yes) echo "true"; return 0 ;;
      n|no)  echo "false"; return 0 ;;
      *)     echo "Please answer y or n." ;;
    esac
  done
}

ask_with_default() {
  local prompt="$1"
  local default="$2"
  local reply
  read -rp "$prompt [$default]: " reply || true
  reply="${reply:-$default}"
  echo "$reply"
}

install_docker_linux() {
  log "Installing Docker Engine on Linux..."
  
  # Detect Linux distribution
  if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    local distro="$ID"
  else
    fatal "Cannot detect Linux distribution. Please install Docker manually."
  fi
  
  case "$distro" in
    ubuntu|debian)
      log "Detected $distro. Installing Docker via apt..."
      sudo apt-get update
      sudo apt-get install -y ca-certificates curl gnupg
      sudo install -m 0755 -d /etc/apt/keyrings
      curl -fsSL https://download.docker.com/linux/$distro/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
      sudo chmod a+r /etc/apt/keyrings/docker.gpg
      
      echo \
        "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$distro \
        $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
        sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
      
      sudo apt-get update
      sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
      
      # Start and enable Docker
      sudo systemctl start docker
      sudo systemctl enable docker
      
      # Add current user to docker group
      sudo usermod -aG docker "$USER"
      
      log "Docker installed successfully!"
      log "IMPORTANT: You need to log out and back in for group changes to take effect."
      log "Or run: newgrp docker"
      ;;
    
    centos|rhel|fedora)
      log "Detected $distro. Installing Docker via yum/dnf..."
      sudo yum install -y yum-utils
      sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
      sudo yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
      
      sudo systemctl start docker
      sudo systemctl enable docker
      sudo usermod -aG docker "$USER"
      
      log "Docker installed successfully!"
      log "IMPORTANT: You need to log out and back in for group changes to take effect."
      ;;
    
    *)
      fatal "Unsupported Linux distribution: $distro. Please install Docker manually: https://docs.docker.com/engine/install/"
      ;;
  esac
}

check_prereqs() {
  log "Checking required commands..."

  command_exists git     || fatal "git is not installed. Please install git and rerun."
  
  # Check for Docker
  if ! command_exists docker; then
    log "Docker Engine required but not installed."
    
    # Detect OS
    local os_type="$(uname -s)"
    
    if [[ "$os_type" == "Darwin" ]]; then
      # macOS - Docker Desktop required
      echo ""
      echo "Docker Desktop is required for macOS."
      echo "Please download and install Docker Desktop from:"
      echo "  https://www.docker.com/products/docker-desktop"
      echo ""
      echo "After installation:"
      echo "  1. Open Docker Desktop"
      echo "  2. Wait for it to start (Docker icon in menu bar)"
      echo "  3. Re-run this script"
      echo ""
      fatal "Please install Docker Desktop and rerun."
    elif [[ "$os_type" == "Linux" ]]; then
      # Linux - offer to auto-install
      local should_install
      should_install="$(ask_yes_no "Would you like to install Docker Engine now?" "y")"
      
      if [[ "$should_install" == "true" ]]; then
        install_docker_linux
      else
        echo ""
        echo "Please install Docker Engine manually:"
        echo "  https://docs.docker.com/engine/install/"
        echo ""
        fatal "Please install Docker Engine and rerun."
      fi
    else
      fatal "Unsupported OS: $os_type. Please install Docker manually and rerun."
    fi
  fi

  # docker compose (plugin) or docker-compose (v1) is fine
  if docker compose version >/dev/null 2>&1; then
    export AVST_DOCKER_COMPOSE="docker compose"
  elif command_exists docker-compose; then
    export AVST_DOCKER_COMPOSE="docker-compose"
  else
    fatal "Neither 'docker compose' nor 'docker-compose' is available. Install Docker Compose and rerun."
  fi

  # Check that Docker daemon is running
  if ! docker info >/dev/null 2>&1; then
    fatal "Docker daemon is not running or not accessible. Start Docker and rerun."
  fi

  log "Basic prerequisites OK."
}

check_gpu_support() {
  log "Checking GPU / NVIDIA setup..."

  if ! command_exists nvidia-smi; then
    fatal "nvidia-smi not found. Install NVIDIA drivers and nvidia-smi on the host, then rerun."
  fi

  # Quick runtime test via CUDA base image
  if ! docker run --rm --gpus all nvidia/cuda:12.2.0-base-ubuntu22.04 nvidia-smi >/dev/null 2>&1; then
    fatal "Docker cannot access GPUs. Install NVIDIA Container Toolkit (nvidia-docker) and rerun."
  fi

  log "GPU & NVIDIA Container Toolkit look OK."
}

clone_or_update_repo() {
  local install_dir="$1"

  if [[ -d "$install_dir/.git" ]]; then
    log "Repository already exists at $install_dir. Updating..."
    (
      cd "$install_dir"
      
      # Check for local changes
      if ! git diff-index --quiet HEAD -- 2>/dev/null || [[ -n $(git ls-files --others --exclude-standard 2>/dev/null) ]]; then
        log "Detected local changes in repository."
        log "Resetting to clean state before update..."
        git reset --hard HEAD
        git clean -fd
      fi
      
      git pull --rebase
    )
  else
    log "Cloning repository into $install_dir..."
    mkdir -p "$install_dir"
    git clone "$APP_GIT_URL" "$install_dir"
  fi
}

validate_audio_path() {
  local audio_path="$1"
  
  # Check if path exists
  if [[ ! -d "$audio_path" ]]; then
    echo ""
    echo "WARNING: Specified folder does not exist: $audio_path"
    local proceed
    proceed="$(ask_yes_no "Would you like to proceed with this folder?" "n")"
    
    if [[ "$proceed" != "true" ]]; then
      return 1  # Validation failed
    fi
    return 0  # User chose to proceed anyway
  fi
  
  # Check if path is accessible (readable)
  if [[ ! -r "$audio_path" ]]; then
    echo ""
    echo "WARNING: Specified folder is not accessible (no read permissions): $audio_path"
    local proceed
    proceed="$(ask_yes_no "Would you like to proceed with this folder?" "n")"
    
    if [[ "$proceed" != "true" ]]; then
      return 1  # Validation failed
    fi
    return 0  # User chose to proceed anyway
  fi
  
  # Path exists and is accessible
  log "Audio path validated: $audio_path"
  return 0
}

generate_env_file() {
  local install_dir="$1"
  local enable_stt="$2"
  local enable_summarization="$3"
  local enable_callback="$4"
  local audio_path="$5"
  local api_port="$6"
  local default_callback_url="$7"

  local env_path="$install_dir/$ENV_FILE_NAME"

  log "Writing environment file: $env_path"

  cat > "$env_path" <<EOF
# Generated by install.sh for avst-service
# You can edit this file manually later if needed.

# Core connectivity
REDIS_URL=redis://redis:6379/0

# API port (external mapping is configured in docker-compose file)
API_PORT=${api_port}

# Audio path inside container; host mapping is configured in docker-compose file
AUDIO_HOST_PATH=${audio_path}

# Whisper STT configuration
WHISPER_MODEL=large-v3
WHISPER_DEVICE=cuda:0
WHISPER_COMPUTE_TYPE=float16

# Future LLM configuration (currently dummy usage)
LLM_DEVICE=cuda:1

# Callback behavior
DEFAULT_CALLBACK_URL=${default_callback_url}
CALLBACK_TIMEOUT_SECONDS=30
CALLBACK_RETRY_COUNT=3
CALLBACK_RETRY_DELAY_SECONDS=3

# Feature toggles
ENABLE_STT=${enable_stt}
ENABLE_SUMMARIZATION=${enable_summarization}
ENABLE_CALLBACK=${enable_callback}
EOF

  log "Environment file created."
}

print_summary() {
  local install_dir="$1"
  local enable_stt="$2"
  local enable_summarization="$3"
  local enable_callback="$4"
  local api_port="$5"
  local audio_path="$6"
  local compose_files="$7"
  local install_mode="$8"

  cat <<EOF

========================================
 avst-service installation summary
========================================
Install directory:  ${install_dir}
Env file:           ${install_dir}/${ENV_FILE_NAME}
Compose files:      ${compose_files}
Mode:               ${install_mode}

Features:
  Whisper STT:      ${enable_stt}
  Summarisation:    ${enable_summarization}
  HTTP callbacks:   ${enable_callback}

Runtime:
  API port (host):  ${api_port}
  Audio host path:  ${audio_path}

EOF

  if [[ "$install_mode" == "testing" ]]; then
    cat <<'EOF'
Testing mode notes:
  - All feature flags are disabled (ENABLE_STT=false, ENABLE_SUMMARIZATION=false, ENABLE_CALLBACK=false).
  - The app uses dummy implementations (no GPU required).
  - docker-compose.testing.yml is typically CPU-only and safe for local/dev runs.

EOF
  else
    if [[ "$enable_stt" == "true" || "$enable_summarization" == "true" ]]; then
      cat <<'EOF'
Production mode notes:
  - GPU-dependent features are enabled; make sure worker service has GPU access
    configured in the compose file (e.g. device requests / --gpus all).
EOF
      echo
    fi
  fi

  cat <<EOF
Next steps:
  1) Ensure your compose file references the env file:

     In your compose files, under 'services:':

       services:
         api:
           # ...
           env_file:
             - ${ENV_FILE_NAME}

         worker:
           # ...
           env_file:
             - ${ENV_FILE_NAME}

     Also make sure the worker service mounts the audio folder, for example:

       services:
         worker:
           # ...
           volumes:
             - "\${AUDIO_HOST_PATH}:/mnt/audio:ro"

  2) Start the stack (if not already started):

       cd ${install_dir}
       ${AVST_DOCKER_COMPOSE} ${compose_files} up -d --build

  3) Check health:

       curl http://localhost:${api_port}/health

  4) Tail logs:

       cd ${install_dir}
       ${AVST_DOCKER_COMPOSE} ${compose_files} logs -f api
       ${AVST_DOCKER_COMPOSE} ${compose_files} logs -f worker

You can re-run install.sh safely to regenerate ${ENV_FILE_NAME}
(if you want to change feature flags, audio path, or port).
EOF
}

parse_args() {
  for arg in "$@"; do
    case "$arg" in
      --testing|--test-mode)
        INSTALL_MODE="testing"
        # Detect macOS and use standalone mac compose file
        if [[ "$(uname -s)" == "Darwin" ]]; then
          COMPOSE_FILE_NAME="docker-compose.mac.yml"
          COMPOSE_FILES="-f docker-compose.mac.yml"
        else
          COMPOSE_FILE_NAME="docker-compose.testing.yml"
          COMPOSE_FILES="-f docker-compose.yml -f docker-compose.testing.yml"
        fi
        ;;
      --prod|--production)
        INSTALL_MODE="prod"
        COMPOSE_FILE_NAME="docker-compose.prod.yml"
        COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
        ;;
      *)
        ;;
    esac
  done
}

# ---------- main ----------

parse_args "$@"

log "AVST Transcriber Service installer"
echo "Mode: ${INSTALL_MODE}"
echo
echo "This script will:"
echo "  - Clone or update the avst-service repository"
if [[ "$INSTALL_MODE" == "testing" ]]; then
  echo "  - Use testing mode (all features disabled, dummy implementations)"
  echo "  - Use ${COMPOSE_FILE_NAME} for docker compose"
else
  echo "  - Ask which features to enable (STT, summarisation, callbacks)"
  echo "  - Optionally verify GPU/NVIDIA setup"
  echo "  - Use ${COMPOSE_FILE_NAME} for docker compose"
fi
echo "  - Generate an env file with correct flags and settings"
echo

check_prereqs

INSTALL_DIR="$(ask_with_default "Installation directory" "$DEFAULT_INSTALL_DIR")"
# Expand tilde to home directory if present
INSTALL_DIR="${INSTALL_DIR/#\~/$HOME}"
clone_or_update_repo "$INSTALL_DIR"

AUDIO_PATH="$(ask_with_default "Host path to mounted audio folder" "$DEFAULT_AUDIO_PATH")"
# Expand tilde in audio path as well
AUDIO_PATH="${AUDIO_PATH/#\~/$HOME}"

# Validate audio path and re-prompt if user declines
while ! validate_audio_path "$AUDIO_PATH"; do
  echo ""
  log "Please specify a different audio folder path."
  AUDIO_PATH="$(ask_with_default "Host path to mounted audio folder" "$DEFAULT_AUDIO_PATH")"
  AUDIO_PATH="${AUDIO_PATH/#\~/$HOME}"
done

API_PORT="$(ask_with_default "API port on host" "$DEFAULT_API_PORT")"

if [[ "$INSTALL_MODE" == "testing" ]]; then
  # Testing mode: everything disabled, no GPU checks
  ENABLE_STT="false"
  ENABLE_SUMMARIZATION="false"
  ENABLE_CALLBACK="false"
  DEFAULT_CALLBACK_URL=""
  log "Testing mode: all ENABLE_* flags will be set to false, skipping GPU checks."
else
  # Production / normal mode: interactive feature toggles
  ENABLE_STT="$(ask_yes_no "Enable Whisper STT (requires GPU + NVIDIA Container Toolkit)?" "y")"
  ENABLE_SUMMARIZATION="$(ask_yes_no "Enable summarisation (LLM, currently dummy but treated as GPU-bound)?" "n")"
  ENABLE_CALLBACK="$(ask_yes_no "Enable HTTP callbacks to your backend?" "y")"

  DEFAULT_CALLBACK_URL=""
  if [[ "$ENABLE_CALLBACK" == "true" ]]; then
    DEFAULT_CALLBACK_URL="$(ask_with_default "Default callback URL (leave empty to require per-request)" "")"
  fi

  # If any GPU feature is enabled, run GPU checks
  if [[ "$ENABLE_STT" == "true" || "$ENABLE_SUMMARIZATION" == "true" ]]; then
    check_gpu_support
  else
    log "GPU-dependent features disabled; skipping GPU checks."
  fi
fi

generate_env_file "$INSTALL_DIR" "$ENABLE_STT" "$ENABLE_SUMMARIZATION" "$ENABLE_CALLBACK" "$AUDIO_PATH" "$API_PORT" "$DEFAULT_CALLBACK_URL"

# In testing mode, create necessary files for bind mounts
if [[ "$INSTALL_MODE" == "testing" ]]; then
  log "Preparing testing mode files..."
  # Create testing_output.log as a file (not directory) for Docker bind mount
  touch "$INSTALL_DIR/testing_output.log"
  # Create test_audio directory if it doesn't exist
  mkdir -p "$INSTALL_DIR/test_audio"
  log "Testing mode files prepared."
fi

# Optional: ask whether to start stack now
SHOULD_START="$(ask_yes_no "Start Docker stack now (${AVST_DOCKER_COMPOSE} ${COMPOSE_FILES} up -d --build)?" "y")"

if [[ "$SHOULD_START" == "true" ]]; then
  log "Starting Docker stack..."
  (
    cd "$INSTALL_DIR"
    ${AVST_DOCKER_COMPOSE} ${COMPOSE_FILES} up -d --build
  )
  log "Docker stack started."
else
  log "Skipping automatic start. You can start later with:"
  echo "  cd $INSTALL_DIR && ${AVST_DOCKER_COMPOSE} -f ${COMPOSE_FILE_NAME} up -d --build"
fi

print_summary "$INSTALL_DIR" "$ENABLE_STT" "$ENABLE_SUMMARIZATION" "$ENABLE_CALLBACK" "$API_PORT" "$AUDIO_PATH" "$COMPOSE_FILES" "$INSTALL_MODE"