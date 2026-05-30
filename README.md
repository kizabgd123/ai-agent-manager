# AI Agent Manager

Mood-based music recommendation system powered by AnythingLLM, integrated with Supabase (pgvector) and deployed via Vercel serverless functions.

```
User text → mood_analyzer → mood → music_recommender → playlist seeds
                                                           ↓
User ←──────── AnythingLLM (Groq/Gemini + RAG) ←───────────┘
```

## Architecture

```
┌──────────────┐     ┌─────────────────────────────────────┐
│  Vercel API  │     │  Hugging Face Space (AnythingLLM)   │
│              │     │                                     │
│  POST /mood  │────>│  Agent Tools:                       │
│  POST /music │     │  • mood_analyzer   → /api/mood      │
│              │     │  • music_recommender → /api/music   │
└──────────────┘     │  • Primary LLM: Groq (Llama 3)     │
                     │  • Backup LLM:  Gemini              │
                     │  • Vector DB:   Supabase pgvector   │
                     └──────────────┬──────────────────────┘
                                    │
                           ┌────────v────────┐
                           │  Supabase       │
                           │  • journal_     │
                           │    entries      │
                           │  • embeddings   │
                           │    (1536d)      │
                           └─────────────────┘
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run tests
python -m pytest tests/ -v

# 3. Deploy Vercel functions
./scripts/deploy.sh
```

## Vercel Deployment

```bash
npm i -g vercel
vercel deploy --prod
```

After deployment, you get two endpoints:

- `https://<project>.vercel.app/api/mood` — `POST {"text": "..."}` → `{"mood", "polarity"}`
- `https://<project>.vercel.app/api/music_trigger` — `POST {"mood": "positive|neutral|negative"}` → `{"recommendations"}`

## AnythingLLM Agent Tools

Register these tools in AnythingLLM Workspace → Agent Tools:

### 1. `mood_analyzer`

| Field | Value |
|---|---|
| Type | HTTP |
| Method | POST |
| URL | `https://<project>.vercel.app/api/mood` |
| Body | `{"text": "<user input>"}` |
| Response | `{"mood": "positive", "polarity": 0.5, "trace_id": "...", ...}` |

### 2. `music_recommender`

| Field | Value |
|---|---|
| Type | HTTP |
| Method | POST |
| URL | `https://<project>.vercel.app/api/music_trigger` |
| Body | `{"mood": "<mood from step 1>"}` |
| Response | `{"mood": "positive", "recommendations": ["focus-pop", ...], "trace_id": "..."}` |

The agent tool definitions are pre-configured in `anythingllm/agent_tools.json` — update the `url` field with your actual Vercel URL.

## Hugging Face Space

1. Create a new Space at https://huggingface.co/new-space
2. SDK: **Docker**
3. Use `anythingllm/Dockerfile`
4. Set repository secrets (see `.env.example` for all required variables)

## Supabase

Run `supabase/init.sql` in your Supabase SQL editor to create:

- `journal_entries` table with pgvector embedding support
- Cosine similarity search function `match_journal_entries()`
- Row Level Security policies

## Project Structure

```
ai-agent-manager/
├── api/
│   ├── mood.py              # Sentiment analysis endpoint
│   └── music_trigger.py     # Music recommendation endpoint
├── anythingllm/
│   ├── Dockerfile            # HF Space deployment
│   ├── agent_tools.json      # Pre-configured agent tools
│   └── README.md             # HF Space README
├── supabase/
│   └── init.sql              # Database schema + pgvector
├── scripts/
│   └── deploy.sh             # One-command deployment
├── tests/
│   └── test_api.py           # API tests
├── .github/workflows/
│   └── ci.yml                # CI + auto-deploy
├── .env.example              # Environment variable template
├── vercel.json               # Vercel configuration
├── pyproject.toml            # Python project config
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GROQ_API_KEY` | Yes | Primary LLM provider |
| `GEMINI_API_KEY` | No | Backup LLM provider |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | Supabase anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service role key |
| `SUPABASE_DB_URL` | Yes | PostgreSQL connection string |
| `APP_PASSWORD` | Yes | AnythingLLM admin password |
| `JWT_SECRET` | Yes | JWT signing secret |
