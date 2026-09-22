# Environment Variables Documentation

This document maintains the complete specifications, purposes, default values, and requirements for all environment variables used in **Prospector AI / Project Heimdall**.

---

## 🗄️ Database Configuration

| Variable Name | Type | Required | Default / Fallback | Description |
| :--- | :--- | :--- | :--- | :--- |
| `DATABASE_URL` | String | Yes | `sqlite:///./lead_intelligence.db` | Connection string for SQLAlchemy ORM. Supports SQLite locally and Supabase PostgreSQL in production. |

---

## 🔑 AI Models & LLM APIs

| Variable Name | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `GEMINI_API_KEY` | String | **Yes** | `""` | Primary LLM key for hybrid intent scoring, verbatim quote validation, and AI verdict generation. |
| `CLAUDE_API_KEY` | String | Optional | `""` | Anthropic Claude API key for high-converting sales pitch generation in Pitcher Mode. |
| `GROQ_API_KEY` | String | Optional | `""` | Groq Llama-3 API key for fast inference in outreach generation. |
| `OPENROUTER_API_KEY` | String | Optional | `""` | OpenRouter API key for fallback open-source LLM inferencing (Qwen, DeepSeek). |
| `MISTRAL_API_KEY` | String | Optional | `""` | Mistral AI API key for fast content summarization. |

---

## 🌐 Intent Discovery & Search APIs

| Variable Name | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `EXA_API_KEY` | String | **Yes** | `""` | Exa.ai neural search API key for public intent signal discovery sweeps. |
| `SERPER_API_KEY` | String | Optional | `""` | Serper Google Search API key for web discovery & news searching. |
| `NEWS_API_KEY` | String | Optional | `""` | NewsAPI key for company growth, funding, and expansion news signals. |

---

## 📱 Social & Job Signal Extraction

| Variable Name | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `SCRAPEBADGER_API_KEY` | String | Optional | `""` | ScrapeBadger key for scraping LinkedIn posts, profiles, and X/Twitter signals. |
| `SCRAPE_CREATORS_API_KEY` | String | Optional | `""` | Scrape Creators API key for multi-platform social post discovery. |
| `APIFY_API_KEY` | String | Optional | `""` | Apify key for web scrapers (JobSpy, company profile scraping). |
| `APIFY_INSIGHTS_API_KEY` | String | Optional | `""` | Secondary Apify key for company hiring insights. |
| `HARVEST_API_KEY` | String | Optional | `""` | Harvest API key for job opening extraction via Apify. |
| `THEIRSTACK_API_KEY` | String | Optional | `""` | TheirStack API key for company tech stack change signals. |
| `ZYTE_API_KEY` | String | Optional | `""` | Zyte API key for automatic job extraction & career page scraping. |

---

## 👤 Contact Enrichment & Integrations

| Variable Name | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `FULLENRICH_API_KEY` | String | Optional | `""` | FullEnrich API key for decision-maker contact & email enrichment. |
| `LINKUP_API_KEY` | String | Optional | `""` | LinkUp API key for executive search and profile resolution. |
| `AIRTABLE_API_KEY` | String | Optional | `""` | Airtable Personal Access Token for exporting scored leads. |
| `AIRTABLE_BASE_ID` | String | Optional | `""` | Base ID for Airtable sync. |
| `AIRTABLE_TABLE_NAME` | String | Optional | `testing-2` | Table name for Airtable lead export sync. |

---

## 🚀 Apache Kafka / Aiven Cloud Streaming

| Variable Name | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `KAFKA_BOOTSTRAP_SERVERS` | String | Optional | `localhost:9092` | Broker host & port for Apache Kafka event streaming (e.g. `kafka-2b8b596a-courage9605-e047.j.aivencloud.com:10152`). |
| `KAFKA_SECURITY_PROTOCOL` | String | Optional | `PLAINTEXT` | Security protocol (`SASL_SSL`, `SSL`, `PLAINTEXT`). Set to `SASL_SSL` for Aiven Cloud Kafka. |
| `KAFKA_SASL_MECHANISM` | String | Optional | `PLAIN` | SASL authentication mechanism (`PLAIN`, `SCRAM-SHA-256`, `SCRAM-SHA-512`). |
| `KAFKA_SASL_USER` | String | Optional | `""` | SASL username for cloud cluster authentication (`avnadmin`). |
| `KAFKA_SASL_PASSWORD` | String | Optional | `""` | SASL password for cloud cluster authentication. |
| `PUBLIC_WEBHOOK_URL` | String | Optional | `""` | Public HTTPS domain for FullEnrich webhook callbacks (e.g. ngrok domain locally or Render URL in production). |

---

## 💻 Frontend Environment Variables

| Variable Name | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `VITE_API_BASE_URL` | String | Optional | `/api` | Base URL for FastAPI backend endpoints. (Defaults to Vite proxy `/api` in local dev). |

---

## 📄 Example `.env` Template

A template file is available at `backend/.env.example`. Copy it to `backend/.env` to configure your environment:

```bash
cp backend/.env.example backend/.env
```
