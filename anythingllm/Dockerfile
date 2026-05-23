# Hugging Face Space Dockerfile for AnythingLLM
# Exposes port 7860 as required by HF Spaces

FROM mintplexlabs/anythingllm:latest

ENV PORT=7860
EXPOSE 7860

# Runtime environment variables should be configured in HF Space Secrets:
# GROQ_API_KEY
# GEMINI_API_KEY
# SUPABASE_URL
# SUPABASE_ANON_KEY
# SUPABASE_SERVICE_ROLE_KEY
# SUPABASE_DB_URL
# APP_PASSWORD
# JWT_SECRET

CMD ["/bin/sh", "-c", "node /app/server.js"]
