# ExamsGen — ACCA TX(VNM) Question Generator

AI-powered web app to generate ACCA TX(VNM) exam-standard questions about Vietnam taxation.

## Quick Start for Claude Code

Read [`docs/CLAUDE-BRIEF.md`](docs/CLAUDE-BRIEF.md) for full technical specifications.

## Overview

- **Part 1:** MCQ questions (CIT, VAT, PIT, FCT, Tax Admin, Transfer Pricing)
- **Part 2:** 10-mark scenario questions (Q1-Q4)
- **Part 3:** 15-mark long-form questions (Q5-Q6)

## Tech Stack

- Backend: Python FastAPI
- Frontend: React + Tailwind CSS
- Database: PostgreSQL
- AI: Claudible API → Anthropic fallback → OpenAI fallback
- Deploy: Docker on VPS via Traefik

## Environment Variables

See `docs/CLAUDE-BRIEF.md` for full env var list.
