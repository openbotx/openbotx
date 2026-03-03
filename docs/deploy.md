# Deploy

OpenBotX supports one-click deploy on multiple cloud platforms. Each platform reads specific configuration files from the repository to build and run the application automatically.

All platforms use the same `Dockerfile` to build the application. The build process has two stages:

1. **Frontend** — builds the Vue 3 web client using Node.js
2. **Backend** — installs Python dependencies, Chromium (for the browser tool), and initializes the project with `openbotx init`

The container listens on the port defined by the `PORT` environment variable (defaults to `8000`).

After deploying on any platform, you need to:

1. Set your LLM provider API key as an environment variable (e.g. `ANTHROPIC_API_KEY`)
2. Access the web interface at the URL provided by the platform
3. Log in with `admin` / `admin`

## Shared Files

### `Dockerfile`

Multi-stage Docker build used by all platforms.

- **Stage 1** (`node:22-alpine`): installs npm dependencies and builds the Vue 3 frontend
- **Stage 2** (`python:3.11-slim`): installs Chromium and system libraries for headless browser support, installs the Python package with UV, and runs `openbotx init` to scaffold the project

The `CMD` respects the platform's `PORT` environment variable:

```
CMD ["sh", "-c", "openbotx start --no-browser --port ${PORT:-8000}"]
```

### `.dockerignore`

Excludes development files, build artifacts, docs, and other non-runtime files from the Docker build context to keep the image small and the build fast.

## Render

**Website:** https://render.com

**Config file:** `render.yaml`

**Deploy button:**

```
https://render.com/deploy?repo=https://github.com/openbotx/openbotx
```

### How it works

1. User clicks the deploy button in the README
2. Render reads `render.yaml` (Blueprint spec) from the repository
3. It builds the Docker image using the `Dockerfile`
4. The service starts on the `free` plan with a public URL
5. Render sets the `PORT` environment variable to `8000`

### Configuration

| Field | Value | Description |
|---|---|---|
| `type` | `web` | Web service with HTTP routing |
| `runtime` | `docker` | Uses the Dockerfile for building |
| `dockerfilePath` | `./Dockerfile` | Path to the Dockerfile |
| `plan` | `free` | Uses the free tier |
| `envVars.PORT` | `8000` | Port the server listens on |

### Environment variables

Set these in the Render dashboard under your service's **Environment** tab:

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (or another provider key) | API key for the LLM provider |
| `PORT` | No (default `8000`) | Port the server listens on |

## Heroku

**Website:** https://heroku.com

**Config files:** `app.json` + `heroku.yml`

**Deploy button:**

```
https://www.heroku.com/deploy?template=https://github.com/openbotx/openbotx
```

### How it works

1. User clicks the deploy button in the README
2. Heroku reads `app.json` for app metadata and detects `"stack": "container"`
3. It reads `heroku.yml` to know how to build the Docker image
4. The Docker image is built using the `Dockerfile`
5. The service starts and Heroku assigns a public URL
6. Heroku dynamically sets the `PORT` environment variable

### Configuration

**`app.json`** — defines the app for the deploy button:

| Field | Value | Description |
|---|---|---|
| `name` | `OpenBotX` | Application name |
| `stack` | `container` | Uses Docker instead of buildpacks |
| `repository` | GitHub URL | Source repository |

**`heroku.yml`** — tells Heroku how to build:

| Field | Value | Description |
|---|---|---|
| `build.docker.web` | `Dockerfile` | Dockerfile for the web process |

### Environment variables

Set these in the Heroku dashboard under **Settings > Config Vars**:

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (or another provider key) | API key for the LLM provider |
| `PORT` | No (set by Heroku) | Port the server listens on |

## DigitalOcean App Platform

**Website:** https://cloud.digitalocean.com

**Config file:** `.do/deploy.template.yaml`

**Deploy button:**

```
https://cloud.digitalocean.com/apps/new?repo=https://github.com/openbotx/openbotx/tree/main
```

### How it works

1. User clicks the deploy button in the README
2. DigitalOcean reads `.do/deploy.template.yaml` from the repository
3. It builds the Docker image using the `Dockerfile`
4. The service starts on a `basic-xxs` instance with a public URL
5. DigitalOcean routes HTTP traffic to port `8000`

### Configuration

The file requires a top-level `spec:` key. Without it, the deploy button does not work.

| Field | Value | Description |
|---|---|---|
| `spec.name` | `openbotx` | Application name |
| `spec.services[0].name` | `web` | Service name |
| `spec.services[0].git.branch` | `main` | Branch to deploy |
| `spec.services[0].git.repo_clone_url` | GitHub `.git` URL | Source repository |
| `spec.services[0].dockerfile_path` | `Dockerfile` | Path to the Dockerfile |
| `spec.services[0].http_port` | `8000` | Port the app listens on |
| `spec.services[0].instance_count` | `1` | Number of instances |
| `spec.services[0].instance_size_slug` | `basic-xxs` | Smallest instance size |

### Environment variables

Set these in the DigitalOcean dashboard under your app's **Settings > App-Level Environment Variables**:

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (or another provider key) | API key for the LLM provider |
| `PORT` | No (default `8000`) | Port the server listens on |

## Railway

**Website:** https://railway.com

**Config file:** `railway.json`

Railway does not support a deploy button that points directly to a GitHub repository URL. Instead, you need to create a template on Railway first, then use the generated template code in the button.

### How to set up

1. Go to [railway.com](https://railway.com) and sign in
2. Click **New Project** and select **Deploy from GitHub repo**
3. Select the `openbotx/openbotx` repository
4. Railway detects the `Dockerfile` and `railway.json` automatically
5. Set your environment variables (e.g. `ANTHROPIC_API_KEY`)
6. Deploy

### Creating a deploy button (optional)

To create a one-click button for others:

1. Go to your [Workspace Templates](https://railway.com/workspace/templates) page
2. Click **New Template** and configure it with the GitHub repo
3. Publish the template to get a template code (e.g. `ZweBXA`)
4. Use the button in your README:

```md
[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/new/template/YOUR_CODE)
```

### Configuration

| Field | Value | Description |
|---|---|---|
| `build.builder` | `DOCKERFILE` | Uses the Dockerfile for building |
| `build.dockerfilePath` | `Dockerfile` | Path to the Dockerfile |
| `deploy.restartPolicyType` | `ON_FAILURE` | Restarts the service if it crashes |
| `deploy.restartPolicyMaxRetries` | `10` | Maximum restart attempts |

### Environment variables

Set these in the Railway dashboard under your service's **Variables** tab:

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (or another provider key) | API key for the LLM provider |
| `PORT` | No (set by Railway) | Port the server listens on |

## File Summary

| File | Platform | Purpose |
|---|---|---|
| `Dockerfile` | All | Multi-stage build (Node.js frontend + Python backend + Chromium) |
| `.dockerignore` | All | Excludes dev files from the Docker build context |
| `render.yaml` | Render | Blueprint service definition |
| `app.json` | Heroku | App metadata and stack declaration for the deploy button |
| `heroku.yml` | Heroku | Docker build instructions |
| `.do/deploy.template.yaml` | DigitalOcean | App Platform service definition (requires `spec:` key) |
| `railway.json` | Railway | Build and deploy configuration (manual setup required) |
