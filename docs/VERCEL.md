# KMRL NexusAI - Vercel Deployment

This repository is split into two deployable parts:

- `frontend/` is a Next.js app and is the part you deploy to Vercel.
- `backend/` is a FastAPI service and should be deployed separately on a Python host such as Render, Railway, Fly.io, or your own infrastructure.

## What is already ready

- The frontend builds successfully with `next build`.
- API rewrites are already configured in `frontend/next.config.js`.
- The app root route already redirects into the dashboard.

## Recommended deployment model

1. Deploy `backend/` first and get a public HTTPS URL.
2. Deploy `frontend/` to Vercel with that backend URL in the environment variables.
3. Point your custom domain at the Vercel project if needed.

## Vercel project settings

Create a new Vercel project and use these settings:

- Framework Preset: `Next.js`
- Root Directory: `.` if deploying the GitHub repository directly
- Alternative Root Directory: `frontend` if you prefer deploying only the frontend folder
- Build Command: `npm run build`
- Output Directory: leave empty
- Install Command: leave default unless your install fails in Vercel

This repository now includes a root `package.json` that forwards Vercel builds to `frontend/`, so importing the repository at its root works correctly.

If install fails in Vercel because of dependency resolution, set:

```bash
npm install --legacy-peer-deps
```

Only use `--ignore-scripts` as a fallback if Vercel specifically fails during package install scripts.

## Required frontend environment variables

Add these in the Vercel project settings:

```bash
NEXT_PUBLIC_API_URL=https://your-backend-domain.example.com
NEXT_PUBLIC_WS_URL=wss://your-backend-domain.example.com
NEXT_PUBLIC_APP_VERSION=2.4.1
NEXT_PUBLIC_APP_NAME=KMRL NexusAI
```

You can start from `frontend/.env.example`.

## Backend requirements before connecting Vercel

The frontend depends on a live backend that exposes:

- `GET /health`
- `POST /api/v1/auth/token`
- `GET /api/v1/kpis`
- `GET /api/v1/fleet`
- `POST /api/v1/copilot/chat`
- `GET /ws/live`

Important: this repo's backend has not been fully dependency-validated in this workspace yet, so you should treat the backend as a separate deployment task from Vercel.

## Local predeploy checklist

Run this from `frontend/`:

```bash
npm install --legacy-peer-deps
npm run type-check
npm run build
```

## Deploy flow

```bash
# from the repository root
cd kmrl/frontend
npm install --legacy-peer-deps
npm run build
```

Then either:

- import the repository into Vercel and set the root directory to `kmrl/frontend`, or
- use the Vercel CLI from `kmrl/frontend`.

## After deploy

Verify these routes in the deployed frontend:

- `/`
- `/dashboard`
- `/analytics`
- `/alerts`
- `/depot`
- `/settings`

Then verify the frontend can successfully reach:

- `${NEXT_PUBLIC_API_URL}/health`
- `${NEXT_PUBLIC_API_URL}/api/v1/kpis`

## Notes

- `frontend/next.config.js` already proxies `/api/v1/*` and `/health` to `NEXT_PUBLIC_API_URL`.
- If the backend uses a different WebSocket origin, keep `NEXT_PUBLIC_WS_URL` aligned with that backend host.
- If you want a single-domain setup, keep the frontend on Vercel and place the backend behind its own HTTPS domain.
