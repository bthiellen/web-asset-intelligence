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

## Setup & Running

1. **Install dependencies**:
   ```bash
   pip install pydantic neo4j python-dotenv
   ```

2. **Configure environment (Optional)**:
   Ensure you have a local Neo4j instance running (Community or Enterprise edition). Create a `.env` file or export details:
   ```env
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password
   ```

3. **Run Analysis**:
   ```bash
   python -m asset_intel.main example.com
   ```
