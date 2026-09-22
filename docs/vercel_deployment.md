# Deploying the SilentVoix Demo Frontend to Vercel

This guide deploys the Vue 3 application in `vue-next/` to Vercel.

## Important scope

Vercel can host the compiled Vue frontend, but it cannot run the complete
SilentVoix stack from this repository. The full stack also needs FastAPI,
MongoDB, PostgreSQL, Redis, Celery workers, TensorFlow/PyTorch services, model
storage, and WebSocket connections. Those services must run elsewhere.

There are two useful Vercel demo modes:

1. **Frontend showcase:** deploy the UI to show the landing page and frontend
   routes. Backend-dependent screens such as login, model upload, dashboards,
   and live inference will not work until an API is connected.
2. **Connected web demo:** deploy the UI to Vercel and point it at a publicly
   reachable deployment of the FastAPI API and its required services. This is
   the recommended demo setup.

## Prerequisites

- A GitHub repository containing this project.
- A Vercel account linked to GitHub.
- Node.js 20 or newer for local verification.
- For the connected demo, a backend URL using HTTPS and WebSocket support.
- Managed or separately hosted MongoDB, PostgreSQL, and Redis for the API.

The frontend build has been verified with:

```powershell
Set-Location vue-next
npm ci
npm run build
```

The generated `vue-next/dist/` directory is ignored by Git and is produced by
Vercel during deployment.

## Option A: Deploy from the Vercel dashboard

1. Open [vercel.com/new](https://vercel.com/new) and import the GitHub
   repository.
2. Set **Root Directory** to `vue-next`.
3. Confirm the project settings:

   | Setting | Value |
   | --- | --- |
   | Framework Preset | `Vite` |
   | Install Command | `npm install` or `npm ci` |
   | Build Command | `npm run build` |
   | Output Directory | `dist` |
   | Node.js Version | `20.x` or newer |

4. For a frontend-only showcase, deploy without an API variable.
5. For a connected demo, add this environment variable before deploying:

   ```text
   VITE_API_URL=https://your-api.example.com
   ```

   Use the API origin only. Do not add a trailing `/api` unless the deployed
   backend actually exposes all routes under that prefix. In this repository,
   the default API routes are exposed at the API origin, so
   `https://your-api.example.com` is normally correct.

6. Select the environments where the variable applies: **Production** and
   **Preview**. Preview values can point to a staging API.
7. Click **Deploy**.

Vite embeds `VITE_*` values into the browser bundle at build time. Never put
   passwords, database URLs, JWT signing keys, or other secrets in a `VITE_*`
   variable. Anything with that prefix is visible to users of the site.

## Option B: Deploy with the Vercel CLI

From the repository root:

```powershell
npm install -g vercel
vercel login
vercel link
vercel env add VITE_API_URL production
vercel env add VITE_API_URL preview
vercel --prod
```

When prompted for the project directory, use `vue-next`. Alternatively, run
the commands from inside `vue-next`:

```powershell
Set-Location vue-next
vercel
vercel --prod
```

For a local production-like check before pushing:

```powershell
Set-Location vue-next
npm ci
npm run build
npx vite preview
```

## Backend requirements for a connected demo

The existing Docker Compose setup is the local deployment model. For a public
demo, move its services to a Docker-capable host or managed providers. At
minimum, the API needs:

- A public FastAPI URL, for example `https://api.example.com`.
- MongoDB connectivity through `MONGO_URI`.
- PostgreSQL connectivity through `DATABASE_URL`.
- Redis connectivity through `REDIS_URL` when queueing, caching, or rate
  limiting is enabled.
- The ML runtime and worker services if the selected playground features use
  them.
- Persistent storage for uploaded models, datasets, and generated audio.
- Production values for `SECRET_KEY`/`JWT_SECRET_KEY`; never use the example
  credentials from `env.example`.

The API should be started with a production command equivalent to:

```text
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Expose `/health` and verify it returns a healthy response before connecting
Vercel to the API.

### CORS

Add the deployed Vercel origins to the backend CORS configuration. Include the
production domain and, if needed, the preview domain pattern used by your
team. Do not rely on `allow_origins=["*"]` for a production deployment when
credentials or authenticated requests are enabled.

### WebSockets

The frontend uses `/ws/stream` and `/ws/sync`. The API host must support
WebSocket upgrade requests over TLS. A browser page served over HTTPS must use
`wss://`, which the frontend derives automatically when `VITE_API_URL` starts
with `https://`.

Test the connected deployment by opening the browser developer console and
checking that requests go to the API host, not the Vercel host. A failed
WebSocket handshake usually means the API proxy or hosting provider is not
forwarding WebSocket upgrades.

## Browser and hardware limitations

- Camera inference runs in the browser and requires HTTPS plus camera
  permission. The default Vercel domain satisfies the secure-context
  requirement.
- Browser speech/TTS may require a user interaction before audio is allowed.
- An ESP32 or serial device cannot be attached to a Vercel function. The
  serial bridge must run on a local computer or another always-on host and
  connect to the public API over `wss://`.
- Local Docker service names such as `http://backend:8080` and
  `http://ml-tensorflow:8091` work only inside the Compose network. They must
  be replaced by reachable service URLs in a cloud deployment.

## SPA routing

The Vue router uses browser history. Vercel normally serves Vite SPAs
correctly, but if a direct refresh of a route such as `/dashboard` returns a
404, add a `vercel.json` in `vue-next/` with this rewrite:

```json
{
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```

Only add this if route refreshes fail. API calls must still target
`VITE_API_URL`; this rewrite is for frontend navigation, not backend proxying.

## Production checklist

- [ ] Vercel root directory is `vue-next`.
- [ ] `npm run build` succeeds.
- [ ] `VITE_API_URL` is set for the intended Vercel environments.
- [ ] The API `/health` endpoint is publicly reachable.
- [ ] API CORS allows the Vercel production origin.
- [ ] API WebSocket routes work over `wss://`.
- [ ] MongoDB, PostgreSQL, Redis, and model storage are external and persistent.
- [ ] Production secrets are configured only on the backend host.
- [ ] Camera permission and browser speech work on the deployed HTTPS domain.
- [ ] ESP32/serial functionality is documented as a separate bridge, not a
  Vercel capability.

## Troubleshooting

### The site deploys but API requests return 404

Check that `VITE_API_URL` is set in Vercel and redeploy. Because Vite embeds
the variable during build, changing it does not affect an already-built
deployment until a new deployment is created.

### Requests still go to the Vercel domain

The variable was missing at build time or was configured for a different
environment. Inspect the deployment's build environment and redeploy after
correcting it.

### Login fails with a CORS error

Add the exact Vercel origin to the API's CORS settings, including `https://`
and without a trailing slash. Also verify that the API's cookie settings are
appropriate for cross-site HTTPS requests.

### Live sensor training cannot connect

Check the API WebSocket URL in the browser network panel. It should use
`wss://your-api.example.com/ws/stream` or `/ws/sync`, not a Vercel URL that has
no WebSocket backend. Then check the API host's WebSocket proxy configuration.

### Model upload or inference fails after deployment

Confirm that the backend has persistent model storage and that its ML runtime
services are reachable from the API. Vercel only serves the frontend bundle;
it does not provide the model files or Python inference process.
