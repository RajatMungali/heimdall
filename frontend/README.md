# Heimdall Frontend

Vite + React + TypeScript implementation for the staged Heimdall lead intelligence UI.

The mock lead dataset uses the strict `LeadDetailResponse` contract and keeps API-facing names identical across TypeScript interfaces, component props, and rendered mappings:

- `company_name`
- `intent_score`
- `signal_freshness`
- `badge`
- `dns_audit`

## Commands

```bash
npm install
npm run dev
npm run build
```

During local development, Vite proxies `/api/*` requests to `http://127.0.0.1:8000`.
Set `VITE_API_BASE_URL` only when the API is hosted somewhere else.
