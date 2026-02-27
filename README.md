# Phantom Board

Real-time visual dashboard for monitoring and controlling AI agent swarms. Watch agents work, track token usage, and manage multi-agent orchestration through an interactive node graph.

```
┌─────────────────────────────────────────────────────────────┐
│  Phantom Board            ● Connected   12 agents           │
├─────────────────────────────────────────────────────────────┤
│  Active: 8/12  │  Tokens: 1.2M  │  Cost: $4.82  │  45ms   │
├──────────────────────────────────────────┬──────────────────┤
│                                          │  Agent: Coder-01 │
│    ┌──────┐     ┌──────┐                │  Status: working │
│    │Router├────►│Coder │                │                  │
│    └──┬───┘     └──┬───┘                │  ▶  ■  ↺        │
│       │            │                     │                  │
│       ▼            ▼                     │  Tokens: 45,231  │
│    ┌──────┐     ┌──────┐                │  Cost: $0.1847   │
│    │Tester├────►│Deploy│                │                  │
│    └──────┘     └──────┘                │  Latency ~~~~~~~~│
│                                          │          ~~~~~~~~│
├──────────────────────────────────────────┴──────────────────┤
│  Task Queue                                                  │
│  ● Build auth module          coder-01                       │
│  ○ Write unit tests           unassigned                     │
│  ✓ Setup CI pipeline          deploy-01                      │
└─────────────────────────────────────────────────────────────┘
```

## Features

- **Interactive Agent Graph** — Drag, zoom, and click agents on a React Flow canvas with live status indicators
- **Real-time WebSocket Updates** — Sub-second latency for agent state changes, metrics, and task progress
- **Agent Controls** — Start, stop, and restart agents directly from the dashboard
- **Metrics Dashboard** — Live token counts, cost tracking, latency monitoring, and task queue status
- **Detail Panel** — Per-agent stats with latency charts (Recharts) and cost breakdowns
- **Task Queue** — Visual task tracker showing status, assignment, and progress
- **Docker Integration** — Auto-discovers agents running as Docker containers via label filtering
- **Process Adapter** — Also supports managing agents as local subprocesses
- **Dark Theme** — Purpose-built dark UI for monitoring workflows

## Architecture

```
┌─────────────┐     WebSocket      ┌─────────────┐
│   Frontend   │◄──────────────────►│   Backend    │
│  React/Vite  │     REST API       │   FastAPI    │
│  React Flow  │──────────────────►│  SQLAlchemy  │
│  Recharts    │                    │  WebSocket   │
└─────────────┘                    └──────┬───────┘
                                          │
                              ┌───────────┼───────────┐
                              │           │           │
                         ┌────▼───┐  ┌────▼───┐  ┌───▼────┐
                         │ Docker │  │Process │  │ Redis  │
                         │Adapter │  │Adapter │  │ Cache  │
                         └────────┘  └────────┘  └────────┘
```

**Backend (FastAPI + Python)**
- Async SQLAlchemy with SQLite for persistence
- WebSocket manager with heartbeat, topic subscriptions, and auto-reconnect
- Agent lifecycle manager with state machine transitions
- Pluggable adapter system (Docker, Process) for agent runtime management
- REST API for CRUD operations on agents, tasks, metrics

**Frontend (React + TypeScript)**
- React Flow for interactive node-graph visualization
- Recharts for latency/metrics charts
- Custom WebSocket hook with auto-reconnect and ping/pong
- TailwindCSS dark theme

## Quick Start

```bash
# Clone and start
git clone https://github.com/KyleBuildsAI/phantom-board.git
cd phantom-board
docker compose up -d

# Open dashboard
open http://localhost
```

### Development Mode

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `API_PORT` | `8000` | Backend API port |
| `UI_PORT` | `80` | Frontend port |
| `DOCKER_HOST` | `unix:///var/run/docker.sock` | Docker socket path |
| `AGENT_LABEL_FILTER` | `phantom.managed=true` | Docker label to discover agents |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost` | Allowed CORS origins |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection URL |

### Docker Agent Labels

Add these labels to your agent containers for auto-discovery:

```yaml
services:
  my-agent:
    image: my-agent:latest
    labels:
      phantom.managed: "true"
      phantom.agent.name: "Coder Agent"
      phantom.agent.type: "worker"    # llm, orchestrator, worker, tool, router
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/api/agents` | List all agents |
| `POST` | `/api/agents` | Register an agent |
| `GET` | `/api/agents/{id}` | Get agent details |
| `PUT` | `/api/agents/{id}` | Update agent |
| `DELETE` | `/api/agents/{id}` | Remove agent |
| `POST` | `/api/agents/{id}/command` | Send command (start/stop/restart) |
| `GET` | `/api/tasks` | List tasks |
| `POST` | `/api/tasks` | Create task |
| `GET` | `/api/metrics` | System metrics |
| `GET` | `/api/metrics/{agent_id}` | Agent metrics history |
| `WS` | `/ws` | Real-time WebSocket |

## Tech Stack

- **Frontend:** React 18, TypeScript, Vite, React Flow, Recharts, TailwindCSS, Lucide Icons
- **Backend:** Python 3.11, FastAPI, SQLAlchemy (async), WebSockets, Docker SDK
- **Infrastructure:** Docker Compose, Redis, Nginx, SQLite

## License

MIT
