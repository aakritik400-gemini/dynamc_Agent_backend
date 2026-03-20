# Dynamic Agent Backend

A lightweight dynamic multi-agent orchestration backend using FastAPI, SQLite, and OpenRouter/LLama3-based agents.

##  Overview

This project provides a REST API to:
- create, update, and list agents
- build agent trees (super-agents with handoffs)
- execute agent chains from a single prompt
- inject text corpus via `data_file`
- enforce a basic guardrail (no credential disclosure)

The system uses:
- FastAPI
- SQLite (`app/db/agents.db` auto-created)
- `agents` package (external dependency) for model orchestration + OpenAI-compatible model runtime

##  Setup

1. Clone repo

```bash
cd c:\Users\Aakriti.kanwal\PROJECT\dynamic_Agent_backend
```

2. (Optional but recommended) activate Python virtual environment

```powershell
# if using provided venv
& .\AGENT\Scripts\Activate.ps1
```

3. Install dependencies

> `requirements.txt` is empty in this repo; ensure your environment has:
> - fastapi
> - uvicorn
> - pydantic
> - python-dotenv
> - sqlite3 (built-in)
> - `agents` package (from pip or local)

```bash
pip install fastapi uvicorn pydantic python-dotenv
# plus agents package/provider
pip install agents
```

4. Set environment variables

Create a `.env` in repository root with:

```ini
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

5. Start app

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

##  API Endpoints

### Health

`GET /`

Response:

```json
{ "message": "Dynamic Multi-Agent System Running" }
```

### Create Agent

`POST /agents`

Body:

```json
{
  "name": "assistant-1",
  "prompt": "You are a finance assistant...",
  "type": "base",            # or "super"
  "data_file": "app/data/f3cd4640-a779-4a0c-9dad-a68d294fdc46_petrochemical.txt"
}
```

### Update Agent

`PUT /agents/{agent_id}`

Body is same as create agent.

### List Agents

`GET /agents`

Response includes all rows from `agents` table.

### Add Handoffs (_super-agent_) 

`POST /agents/{agent_id}/handoffs`

Body:

```json
{ "child_agent_ids": [2, 3] }
```

### Clear DB

`DELETE /agents`

Wipes `agents` and `agent_handoffs` tables.

### Ask Agent

`POST /ask/{agent_id}`

Body:

```json
{ "question": "How do I perform a market analysis?" }
```

Response includes `request_id`, `agent_id`, `agent_name`, and `response`.

##  Database

- `app/db/agents.db` (created automatically)
- `agents` table:
  - `id`, `name`, `prompt`, `type`, `data_file`, `created_at`
- `agent_handoffs` table:
  - `id`, `parent_agent_id`, `child_agent_id`

##  Agent Builder Behavior

- `app.services.agent_builder.build_agent` loads agent record from DB
- if `data_file` given, reads text from path and appends to prompt
- if `type == "super"`, recursion loads all child agents via `agent_handoffs`
- avoids cycles via `visited` set

##  Guardrails

`app.services.input_guardrails.no_credential_disclosure_guardrail` is applied via `run_config`.

##  Example cURL

Create agent:

```bash
curl -X POST http://localhost:8000/agents \
  -H "Content-Type: application/json" \
  -d '{"name":"student-bot","prompt":"Answer student questions.","type":"base"}'
```

Ask:

```bash
curl -X POST http://localhost:8000/ask/1 \
  -H "Content-Type: application/json" \
  -d '{"question":"Explain linear regression."}'
```

##  Notes

- `OPENROUTER_API_KEY` is required or app throws.
- `agents` package must be installed and reachable to import `Agent`, `Runner`, and model classes.
- The `data_file` path is used as-is; missing paths are gracefully treated as empty text.


