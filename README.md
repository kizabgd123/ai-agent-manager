# AI Agent Manager

## Overview

A multi-step AI agent framework for hackathon projects featuring:
- **Research Assistant Agent** (MongoDB Track): Automates literature review by searching, summarizing, and synthesizing academic papers
- **Auto Bug-Fix Workflow**: Detects test/log failures, proposes patches, applies them, and retries safely
- **Gemini 2.5 Flash LLM integration** via a modular adapter
- **Tool-based agent architecture** with function calling support

## Partner Track

**MongoDB** - This project demonstrates an AI Research Assistant that uses MongoDB Atlas for storing and retrieving academic papers with vector search capabilities.

## Problem Solved

Researchers spend hours manually searching, reading, and organizing academic papers. This agent automates the literature review process by:
1. Searching for relevant papers based on research questions
2. Extracting key findings and methodologies  
3. Storing and organizing papers in MongoDB
4. Generating synthesis reports and identifying research gaps

## Quick Start

### Prerequisites

- Python 3.10+
- Google Gemini API key
- MongoDB Atlas connection string (optional)

### Installation

```bash
pip install -r requirements.txt
```

### Environment Setup

```bash
cp .env.example .env
# Edit .env and add your API keys:
# GEMINI_API_KEY=your_key_here
# MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>/<database>
# MONGODB_DATABASE=research_assistant
# MONGODB_COLLECTION=papers
```

### Run the Research Agent

```bash
PYTHONPATH=src python -c "
from llm.factory import create_llm_client
from agent import create_research_agent

llm = create_llm_client()
agent = create_research_agent(llm)
result = agent.execute_research_workflow('What are recent advances in machine learning?', max_papers=3)
print(result['synthesis'])
"
```

### Run Auto Bug-Fix Workflow

```bash
PYTHONPATH=src python -m autobugfix.cli --repo-root . --max-attempts 3
```

### Run Tests

```bash
PYTHONPATH=src python -m pytest -v
```

## Project Structure

```
/workspace
├── src/
│   ├── agent/           # Multi-step AI agents
│   │   ├── __init__.py
│   │   └── research_agent.py    # MongoDB-powered research assistant
│   ├── autobugfix/      # Auto bug-fix workflow
│   │   ├── __init__.py
│   │   ├── cli.py
│   │   └── workflow.py
│   └── llm/             # LLM adapters
│       ├── __init__.py
│       ├── base.py
│       ├── factory.py
│       └── gemini_client.py
├── api/                 # Vercel serverless functions
│   ├── mood.py
│   └── music_trigger.py
├── anythingllm/         # AnythingLLM Docker config
├── tests/               # Test suite
│   ├── test_autobugfix.py
│   └── test_research_agent.py
├── requirements.txt
├── LICENSE              # MIT License
└── README.md
```

## Agent Architecture

### Research Agent Tools

The agent has access to these tools for multi-step reasoning:

1. **search_papers**: Search academic databases for relevant papers
2. **store_paper**: Store paper details in MongoDB
3. **summarize_paper**: Generate concise summaries using LLM
4. **compare_papers**: Compare multiple papers and identify patterns

### Workflow Steps

1. **Analyze** research question and extract key concepts
2. **Search** for relevant papers using generated queries
3. **Process** each paper (summarize, extract metadata)
4. **Store** organized data in MongoDB
5. **Synthesize** findings across all papers
6. **Identify** research gaps and opportunities

## LLM Integration

The project uses Google Gemini 2.5 Flash with:
- Standard text generation
- Function/tool calling for agent workflows
- Configurable temperature and model parameters

Configuration via environment variables:
- `LLM_PROVIDER` (default: `gemini`)
- `LLM_MODEL` (default: `gemini-2.5-flash`)
- `GEMINI_API_KEY` (required)
- `LLM_TEMPERATURE` (default: `0.0`)

### MongoDB configuration

The research agent uses the official MongoDB Python driver. Configure its
endpoint and target with `MONGODB_URI`, `MONGODB_DATABASE` (default:
`research_assistant`), and `MONGODB_COLLECTION` (default: `papers`). If the
URI does not include credentials, set `MONGODB_USERNAME`, `MONGODB_PASSWORD`,
and optionally `MONGODB_AUTH_SOURCE`. `MONGODB_ATLAS_URI` remains supported as
a backwards-compatible alias for `MONGODB_URI`.

Create a MongoDB text index on the `title`, `abstract`, and `keywords` fields
before calling `search_papers`; it uses indexed `$text` search and returns the
highest-scoring records first.

## Deployment

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for detailed cloud deployment instructions including:
- Hugging Face Spaces for AnythingLLM
- Vercel for serverless functions
- Supabase for vector storage
- MongoDB Atlas for document storage

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Hackathon Checklist

- [x] Chosen partner track: **MongoDB**
- [x] Defined real-world problem: Automated literature review for researchers
- [x] Set up Google Cloud account and Gemini API access
- [x] Designed multi-step reasoning workflow (6 steps)
- [x] Integrated MongoDB tool for data persistence
- [x] Agent uses tools beyond simple Q&A (search, store, summarize, compare)
- [x] Tested agent's planning and execution capabilities
- [x] Open-source repository with MIT license
- [ ] Deploy and host agent (see DEPLOYMENT_GUIDE.md)
- [ ] Record demo video
- [ ] Complete Devpost submission
