---
title: AI Agent Manager
emoji: 🧠
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# AI Agent Manager — Hugging Face Space

This is the AnythingLLM backend for the AI Psychologist system.

## Environment Secrets

Set these in your Space settings → Repository secrets:

| Secret | Description |
|---|---|
| `GROQ_API_KEY` | Primary LLM provider |
| `GEMINI_API_KEY` | Backup LLM provider |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key |
| `SUPABASE_DB_URL` | PostgreSQL connection string |
| `APP_PASSWORD` | AnythingLLM admin password |
| `JWT_SECRET` | JWT signing secret |

## Connected Tools

After deployment, register these tools in AnythingLLM Workspace → Agent Tools:

1. **mood_analyzer** → `POST <vercel-url>/api/mood` → analyzes text sentiment
2. **music_recommender** → `POST <vercel-url>/api/music_trigger` → returns playlist seeds
