#!/usr/bin/env bash
# hf_deploy_space.sh — Deploy AnythingLLM to Hugging Face Space using HF API
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

show_help() {
    cat << EOF
Hugging Face Space Deployment Tool

Usage:
  $0 --name <space_name> [options]

Options:
  --name <name>      Name of the Space (required)
  --org <org>        Organization namespace (optional)
  --private          Create as private (default: false)
  --env-file <file>  Path to .env file (default: .env)
  --help             Show this help message

Description:
  Creates or updates a Hugging Face Space for AnythingLLM.
  Uploads anythingllm/Dockerfile and anythingllm/agent_tools.json.
  Sets repository secrets from the provided .env file.

Requirements:
  - HF_TOKEN environment variable must be set.
  - jq must be installed.
EOF
}

# Default values
SPACE_NAME=""
ORG=""
PRIVATE=false
ENV_FILE=".env"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --name)
            SPACE_NAME="$2"
            shift 2
            ;;
        --org)
            ORG="$2"
            shift 2
            ;;
        --private)
            PRIVATE=true
            shift
            ;;
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

if [[ -z "$SPACE_NAME" ]]; then
    echo -e "${RED}Error: --name is required.${NC}"
    show_help
    exit 1
fi

if [[ -z "${HF_TOKEN:-}" ]]; then
    echo -e "${RED}Error: HF_TOKEN environment variable is not set.${NC}"
    exit 1
fi

# ── 1. Create Repository ──────────────────────────────────────────
echo -e "${CYAN}→ Creating/Checking Space: ${SPACE_NAME}...${NC}"

NAMESPACE=""
if [[ -n "$ORG" ]]; then
    NAMESPACE="$ORG/"
fi

# Build payload for repo creation
# We include Dockerfile and agent_tools.json in the creation if possible
DOCKERFILE_CONTENT=$(base64 -w 0 anythingllm/Dockerfile)
TOOLS_CONTENT=$(base64 -w 0 anythingllm/agent_tools.json)

PAYLOAD=$(jq -n \
    --arg name "$SPACE_NAME" \
    --arg org "$ORG" \
    --argjson private "$PRIVATE" \
    --arg docker_b64 "$DOCKERFILE_CONTENT" \
    --arg tools_b64 "$TOOLS_CONTENT" \
    '{
        name: $name,
        type: "space",
        sdk: "docker",
        private: $private,
        files: [
            { path: "Dockerfile", content: $docker_b64, encoding: "base64" },
            { path: "agent_tools.json", content: $tools_b64, encoding: "base64" }
        ]
    } | if $org != "" then . + {organization: $org} else . end')

RESPONSE=$(curl -s -X POST -H "Authorization: Bearer ${HF_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" \
    https://huggingface.co/api/repos/create)

ERROR=$(echo "$RESPONSE" | jq -r '.error // empty')
if [[ -n "$ERROR" ]]; then
    if [[ "$ERROR" == "Repository already exists" ]]; then
        echo -e "${YELLOW}! Space already exists. Proceeding to update secrets...${NC}"
    else
        echo -e "${RED}✗ Error creating repository: $ERROR${NC}"
        echo "$RESPONSE" | jq .
        exit 1
    fi
else
    echo -e "${GREEN}✓ Space created successfully!${NC}"
fi

# ── 2. Set Secrets ────────────────────────────────────────────────
if [[ -f "$ENV_FILE" ]]; then
    echo -e "${CYAN}→ Setting secrets from ${ENV_FILE}...${NC}"
    
    # Get namespace for secret setting
    if [[ -z "$ORG" ]]; then
        # Fetch username if org not provided
        USER_INFO=$(curl -s -H "Authorization: Bearer ${HF_TOKEN}" https://huggingface.co/api/whoami-v2)
        ORG=$(echo "$USER_INFO" | jq -r '.name')
    fi

    # List of keys to sync (from README/Dockerfile)
    SECRET_KEYS=(
        "GROQ_API_KEY"
        "GEMINI_API_KEY"
        "SUPABASE_URL"
        "SUPABASE_ANON_KEY"
        "SUPABASE_SERVICE_ROLE_KEY"
        "SUPABASE_DB_URL"
        "APP_PASSWORD"
        "JWT_SECRET"
    )

    for KEY in "${SECRET_KEYS[@]}"; do
        VALUE=$(grep -E "^${KEY}=" "$ENV_FILE" | cut -d'=' -f2- | sed 's/^"//;s/"$//;s/^\x27//;s/\x27$//')
        if [[ -n "$VALUE" ]]; then
            echo -e "  - Syncing ${KEY}..."
            SECRET_PAYLOAD=$(jq -n --arg key "$KEY" --arg value "$VALUE" '{key: $key, value: $value}')
            curl -s -X POST -H "Authorization: Bearer ${HF_TOKEN}" \
                -H "Content-Type: application/json" \
                -d "$SECRET_PAYLOAD" \
                "https://huggingface.co/api/spaces/${ORG}/${SPACE_NAME}/secrets" > /dev/null
        else
            echo -e "${YELLOW}  ! Skipping ${KEY} (not found in ${ENV_FILE})${NC}"
        fi
    done
    echo -e "${GREEN}✓ Secrets synced.${NC}"
else
    echo -e "${YELLOW}! ${ENV_FILE} not found. Skipping secret sync.${NC}"
fi

echo -e "${GREEN}══════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Space: https://huggingface.co/spaces/${ORG}/${SPACE_NAME}${NC}"
echo -e "${GREEN}══════════════════════════════════════════════${NC}"