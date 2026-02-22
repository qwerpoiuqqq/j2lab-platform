# Quantum Campaign - Reference Code

> **This is REFERENCE CODE ONLY.** It is a read-only copy of the Quantum Campaign Automation
> source code, placed here for architectural reference during unified-platform development.

## Purpose

This directory contains the source code from `quantum-campaign-automation/` to serve as a
reference for building the `campaign-worker` service in the unified platform. Key areas of
interest include:

- **`backend/app/services/superap.py`** - SuperAP API integration (campaign registration)
- **`backend/app/services/campaign_registration.py`** - Campaign registration workflow
- **`backend/app/models/`** - SQLAlchemy data models (campaign, keyword, account, template)
- **`backend/app/modules/`** - Modular step-based automation architecture
- **`backend/app/routers/`** - FastAPI route definitions
- **`frontend/src/`** - React + TypeScript dashboard UI
- **`docs/`** - Architecture decisions, API docs, selector mappings

## What Was Excluded (INTENTIONALLY)

| Excluded Item | Reason |
|---------------|--------|
| **`.env`** | Contains **real superap.io credentials** - never commit or copy |
| **`data/`** | Contains `quantum.db` (25MB) with **LIVE OPERATIONAL DATA** |
| **`data/campaign.db`** | Legacy database file |
| **`logs/`** | Runtime log files, not relevant |
| **`scripts/`** | 60+ standalone test/debug scripts, not needed for reference |
| **`__pycache__/`** | Python bytecode cache |
| **`.git/`** | Git history from the original repo |
| **`node_modules/`** | npm dependencies (install from package.json if needed) |
| **`frontend/dist/`** | Built frontend assets |

## Warnings

1. **DO NOT** create a `.env` file in this directory. Use `.env.example` as a template
   and place real credentials only in the appropriate deployment location.

2. **DO NOT** copy `quantum.db` or any database files here. The live database contains
   real customer campaign data and operational state.

3. **DO NOT** run this code directly. It is meant as a reference for understanding the
   existing architecture and porting logic to the unified platform.

4. **DO NOT** commit credentials or API keys found in the original `.env` to any repository.

## Source

- **Original location:** `C:\Users\82104\Desktop\programming\Naver-project\quantum-campaign-automation\`
- **Copy date:** 2026-02-23
- **Copied by:** Claude Code (automated reference copy)

## File Count

- 146 source files copied (Python, TypeScript, config, documentation)
- Zero database files, zero credential files, zero runtime artifacts
