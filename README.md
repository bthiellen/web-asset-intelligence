# Web Asset Intelligence Platform

A local, modular Web Asset Intelligence platform to map infrastructure and corporate ownership connections between websites using passive OSINT techniques and manual intelligence inputs.

## Features

- **Strict Passive-Only Discovery**: Design excludes active scanning or probing. Uses passive DNS history, Certificate Transparency logs, and tracking ID extraction.
- **Relational Graph Analysis**: Neo4j database schema representation mapping:
  - `Domain` nodes
  - `IP` address nodes
  - `Certificate` details
  - `Entity` (Individuals / Corporate LLCs)
  - `Address` nodes
- **AI/LLM Structured Data Mapper**: Maps raw State Corporation Commission (SCC) or LLC JSON registration files into standardized Neo4j entities.
- **Pydantic Validation**: Strong compile-time/run-time schema enforcement on IP/Domain structures before database insertion.

## Project Structure

```text
asset_intel/
├── README.md
├── requirements.txt
└── asset_intel/
    ├── __init__.py
    ├── main.py                # Analysis engine entrypoint & orchestrator
    ├── collectors/            # Modular OSINT scrapers
    │   ├── __init__.py
    │   ├── base.py            # Base abstract class enforcing passive limits
    │   ├── cert.py            # Certificate logs collector
    │   ├── dns.py             # Passive DNS collector
    │   ├── tracker.py         # Tracker extraction collector
    │   └── manual_filing.py   # Manual/Corporate filing collector
    ├── models/
    │   ├── __init__.py
    │   └── entities.py        # Pydantic schemas (Domain, IP, etc.)
    ├── storage/
    │   ├── __init__.py
    │   ├── database.py        # Neo4j connection and queries
    │   └── schema.py          # Neo4j constraint settings
    └── utils/
        ├── __init__.py
        └── ai_mapper.py       # Corporate filing parser mapping utility
```

## Web Dashboard & Interactive Visualizations

Phase 2 adds a lightweight, mobile-responsive Web UI and API layer:
- **FastAPI Backend**: Exposes endpoints for initiating passive asset intelligence mapping, uploading corporate filings, and querying the current Neo4j database graph.
- **Vis.js Network Graph**: Renders the complete ownership, infrastructure, and location relationships interactively (zoom, pan, search, physics settings, property inspect sidebar).
- **Homelab Ready**: Deployable as a single container stack with automatic database health checks.

## Project Structure (Updated)

```text
asset_intel/
├── README.md
├── requirements.txt
├── app.py                     # FastAPI backend server
├── Dockerfile                 # Docker configuration for FastAPI
├── docker-compose.yml         # Compose stack setup (db + web)
├── static/                    # Frontend visualizer files
│   ├── index.html             # Dashboard layout
│   ├── style.css              # Glassmorphism dark slate UI styles
│   └── app.js                 # Vis.js graph rendering script
└── asset_intel/               # Core packages (collectors, models, etc.)
```

## Setup & Running

### Option A: Local Dev Server

1. **Install requirements**:
   Ensure `python-multipart` and `httpx` are installed alongside standard dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r asset_intel/requirements.txt
   pip install python-multipart httpx
   ```

2. **Configure environment (.env)**:
   Create a `.env` in the root:
   ```env
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=password
   ```

3. **Start the FastAPI App**:
   ```bash
   uvicorn asset_intel.app:app --host 0.0.0.0 --port 8000
   ```
   Open `http://localhost:8000` in your web browser.

### Option B: Homelab Docker Compose (Recommended)

To spin up the entire platform (FastAPI + Neo4j Database) with persistent data volumes:

```bash
# Navigate to the compose directory
cd asset_intel

# Spin up the containers
docker-compose up --build -d
```
- Open **Web Dashboard UI**: `http://localhost:8000`
- Open **Neo4j Browser Console**: `http://localhost:7474` (User: `neo4j`, Password: `password`)

## Verification & Testing

To execute the unit and API integration tests:
```bash
PYTHONPATH=. pytest
```
