#!/usr/bin/env bash
# deploy.sh — One-command deployment: Vercel + Hugging Face Space
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}══════════════════════════════════════════════${NC}"
echo -e "${CYAN}  AI Agent Manager — Deploy${NC}"
echo -e "${CYAN}══════════════════════════════════════════════${NC}"

# ── 1. Validate .env ──────────────────────────────────────────────
if [ ! -f .env ]; then
  echo -e "${RED}✗ .env file not found. Copy .env.example → .env and fill in secrets.${NC}"
  exit 1
fi
echo -e "${GREEN}✓ .env found${NC}"

# ── 2. Deploy Vercel functions ────────────────────────────────────
echo ""
echo -e "${CYAN}→ Deploying Vercel serverless functions...${NC}"
if command -v vercel &> /dev/null; then
  vercel deploy --prod --yes 2>&1 | tee /tmp/vercel_deploy.log
  VERCEL_URL=$(grep -oP 'https://[a-zA-Z0-9.-]+\.vercel\.app' /tmp/vercel_deploy.log | head -1)
  echo -e "${GREEN}✓ Vercel deployed: ${VERCEL_URL:-https://<project>.vercel.app}${NC}"
else
  echo -e "${RED}✗ Vercel CLI not found. Install: npm i -g vercel${NC}"
  echo "  Then run: vercel deploy --prod"
fi

# ── 3. Print AnythingLLM tool config ──────────────────────────────
VERCEL_FINAL="${VERCEL_URL:-https://<your-project>.vercel.app}"
echo ""
echo -e "${CYAN}→ Register these tools in AnythingLLM:${NC}"
echo ""
echo -e "  Tool 1: mood_analyzer"
echo -e "    URL:  ${VERCEL_FINAL}/api/mood"
echo -e "    Body: { \"text\": \"<journal text>\" }"
echo ""
echo -e "  Tool 2: music_recommender"
echo -e "    URL:  ${VERCEL_FINAL}/api/music_trigger"
echo -e "    Body: { \"mood\": \"positive|neutral|negative\" }"
echo ""

# ── 4. Print HF Space instructions ────────────────────────────────
echo -e "${CYAN}→ Hugging Face Space deployment:${NC}"
echo "  1. Create Space at https://huggingface.co/new-space"
echo "     - SDK: Docker"
echo "     - Dockerfile: anythingllm/Dockerfile"
echo "  2. Set Space secrets (HF Settings → Repository secrets):"
echo "     - GROQ_API_KEY, GEMINI_API_KEY"
echo "     - SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_DB_URL"
echo "     - APP_PASSWORD, JWT_SECRET"
echo ""

echo -e "${GREEN}══════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Deployment preparation complete!${NC}"
echo -e "${GREEN}══════════════════════════════════════════════${NC}"
