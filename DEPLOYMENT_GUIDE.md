# Fully Free Cloud-Based AI Psychologist System (Implementation Guide)

_Last updated: 2026-05-23_

This guide shows how to deploy a **zero-cost prototype** using:

- **AnythingLLM** on **Hugging Face Spaces (Docker)**
- **Groq (Llama 3)** as primary LLM
- **Google Gemini API** as backup LLM
- **Supabase + pgvector** for embeddings/knowledge base
- **Vercel Python serverless functions** for mood analysis and music triggers

> Important: "Fully free" means staying inside each provider's free-tier limits. Free-tier policies can change, so verify limits in each dashboard before production use.

---

## 1) Create cloud accounts (free tiers)

Create and verify accounts on:

1. Groq Cloud
2. Google AI Studio / Gemini API
3. Supabase
4. Hugging Face
5. Vercel

Use a password manager and enable 2FA where available.

---

## 2) Groq setup (primary LLM)

1. In Groq Console, create an API key.
2. Save it as:

```bash
GROQ_API_KEY=your_key_here
```

3. Pick a supported Llama 3 family model in AnythingLLM (for example a Llama-3.x chat-capable model exposed by Groq).

---

## 3) Gemini setup (backup LLM)

1. Create an API key in Google AI Studio.
2. Save it as:

```bash
GEMINI_API_KEY=your_key_here
```

3. Keep this key ready for fallback routing in AnythingLLM (if you switch provider during outages/limits).

---

## 4) Supabase project + pgvector

1. Create a new Supabase project.
2. In SQL editor, enable vector support:

```sql
create extension if not exists vector;
```

3. Collect credentials:

- Project URL (e.g., `https://<project>.supabase.co`)
- `anon` API key
- `service_role` API key (keep secret)
- Database connection string (PostgreSQL URL)

4. Optional table schema for manual checks:

```sql
create table if not exists journal_entries (
  id bigserial primary key,
  created_at timestamptz default now(),
  source text not null,
  content text not null,
  embedding vector(1536)
);
```

---

## 5) Hugging Face Space (AnythingLLM via Docker)

1. Create a **new Space**:
   - SDK: **Docker**
   - Visibility: Private (recommended)
2. Use the official AnythingLLM Docker image in Space config (`Dockerfile`-based setup).
3. Add Space secrets:

- `GROQ_API_KEY`
- `GEMINI_API_KEY` (backup)
- Supabase credentials required by AnythingLLM
- `APP_PASSWORD` (or app-specific auth settings)

4. Enable Space authentication/password protection (Settings → Visibility/Access controls).

---

## 6) Connect LLM + vector DB inside AnythingLLM

In AnythingLLM workspace admin settings:

1. **Primary model provider**: Groq
2. **Model**: Llama 3 variant available in your Groq account
3. **Fallback provider**: Gemini (configure second provider)
4. **Embedding/vector storage**: Supabase pgvector
5. Run connection test from UI.

---

## 7) Upload psychology knowledge

Upload materials into AnythingLLM workspace knowledge base:

- Journal entries (sanitized)
- Psychology books and notes (only content you have legal rights to store/use)

Then trigger embedding/indexing and verify chunks appear in vector store.

---

## 8) Build Vercel Python serverless functions

Create project structure:

```text
api/
  mood.py
  music_trigger.py
requirements.txt
```

### `requirements.txt`

```txt
textblob==0.18.0.post0
```

### `api/mood.py`

```python
from http.server import BaseHTTPRequestHandler
import json
from textblob import TextBlob

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("content-length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        text = payload.get("text", "")

        polarity = TextBlob(text).sentiment.polarity
        if polarity > 0.2:
            mood = "positive"
        elif polarity < -0.2:
            mood = "negative"
        else:
            mood = "neutral"

        response = {
            "mood": mood,
            "polarity": polarity,
            "input_length": len(text)
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))
```

### `api/music_trigger.py`

```python
from http.server import BaseHTTPRequestHandler
import json

PLAYLIST_MAP = {
    "positive": ["focus-pop", "upbeat-acoustic"],
    "neutral": ["lofi-balance", "calm-instrumental"],
    "negative": ["grounding-ambient", "soft-piano"]
}

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("content-length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        mood = payload.get("mood", "neutral")

        response = {
            "mood": mood,
            "recommendations": PLAYLIST_MAP.get(mood, PLAYLIST_MAP["neutral"]),
            "action": "return_playlist_seed"
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode("utf-8"))
```

### Deploy on Vercel

1. Import repo into Vercel.
2. Confirm Python runtime is detected.
3. Deploy.
4. Copy endpoints:

- `https://<project>.vercel.app/api/mood`
- `https://<project>.vercel.app/api/music_trigger`

---

## 9) Register Vercel endpoints as AnythingLLM agent tools

In AnythingLLM tool/agent configuration:

1. Add HTTP tool `mood_analyzer` → `/api/mood`
2. Add HTTP tool `music_recommender` → `/api/music_trigger`
3. Define JSON schemas:
   - Mood tool input: `{ "text": "string" }`
   - Music tool input: `{ "mood": "positive|neutral|negative" }`

Test each tool directly from AnythingLLM UI before linking them in conversational prompts.

---

## 10) End-to-end validation checklist

Run these tests:

1. Ask AI psychologist a domain question grounded in uploaded docs.
2. Confirm retrieved context/citations come from indexed knowledge.
3. Send a journal-like sentence and verify mood tool executes.
4. Verify music tool executes with mood output.
5. Confirm fallback provider works by temporarily switching off Groq key.

Success criteria:

- LLM answers with RAG context
- Tool calls return valid JSON
- No paid-tier usage is triggered

---

## 11) Free-tier monitoring (to keep cost at $0)

Check weekly:

- Groq request/token usage
- Gemini usage quotas
- Supabase DB size, bandwidth, and row growth
- Hugging Face Space hardware/runtime usage
- Vercel function invocations and execution time

Set alert thresholds at ~70–80% of free limits and add automatic rate limiting where possible.

---

## Security and ethics notes

- Do **not** treat this as licensed medical care.
- Add crisis escalation messaging and emergency contact instructions.
- Store minimal personal data, encrypt secrets, and rotate API keys.
- Use explicit user consent for storing journal entries.


---

## 12) Quick API verification command (AnythingLLM `/api/v1/system`)

Use this command to verify runtime settings and print only required fields:

```bash
./fetch_system_fields.sh "https://<your-space>.hf.space" "<YOUR_BEARER_TOKEN>"
```

Expected JSON shape:

```json
{
  "llmProvider": "...",
  "embeddingProvider": "...",
  "vectorDb": "...",
  "version": "..."
}
```

If your environment uses a restrictive outbound proxy and HTTPS CONNECT fails with `403`, run the command from:

- local machine terminal, or
- CI runner/network that can reach `*.hf.space`.
