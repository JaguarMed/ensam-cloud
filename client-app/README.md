# Cloud Platform - Client App

A futuristic web frontend for the GPU-powered Python execution platform.

## Overview

This client application provides:
- **Login Page** - Authenticate with the remote compute server
- **Script Editor** - Write/upload Python code and submit for execution
- **Job History** - View all submitted jobs and their status

The client acts as an API gateway, forwarding requests to the remote compute server.

## Project Structure

```
client-app/
├── app/
│   ├── app.py              # Main FastAPI application
│   ├── auth.py             # JWT authentication helpers
│   ├── api_proxy.py        # API gateway to compute server
│   ├── templates/
│   │   ├── base.html       # Base template with layout
│   │   ├── login.html      # Login page
│   │   ├── editor.html     # Script editor page
│   │   └── history.html    # Job history page
│   ├── static/
│   │   ├── css/
│   │   │   └── styles.css  # Custom styles
│   │   └── js/
│   │       └── app.js      # Core JavaScript
│   └── utils/
│       └── jwt_manager.py  # JWT utilities
├── requirements.txt
└── README.md
```

## Installation

1. **Install dependencies:**
   ```bash
   cd client-app
   pip install -r requirements.txt
   ```

2. **Configure the compute server URL:**
   ```bash
   # Set environment variable (optional, defaults to localhost:8000)
   export COMPUTE_SERVER_URL=http://your-server-ip:8000
   ```

## Running the App

```bash
# From the client-app directory
uvicorn app.app:app --reload --port 3000
```

Then open http://localhost:3000 in your browser.

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `COMPUTE_SERVER_URL` | `http://localhost:8000` | URL of the remote compute server |

## Pages

### Login (`/login`)
- Dark futuristic UI with glassmorphism
- Email and password authentication
- Connects to remote server's `/auth/login` endpoint
- Stores JWT in localStorage

### Script Editor (`/editor`)
- Code editor with syntax highlighting
- Line numbers display
- File upload support (.py files)
- GPU enable/disable toggle
- Submits to remote server's `/api/jobs/run` endpoint

### Job History (`/history`)
- Table view of all submitted jobs
- Status badges (queued, running, finished, failed)
- Job details modal
- Real-time refresh

## API Gateway Routes

The client proxies these requests to the compute server:

| Client Route | Server Route | Description |
|-------------|--------------|-------------|
| `POST /api/auth/login` | `/auth/login` | User authentication |
| `POST /api/jobs/run` | `/api/jobs/run` | Submit a job |
| `GET /api/jobs/history` | `/api/jobs/history` | Get job history |
| `GET /api/jobs/{id}` | `/api/jobs/{id}` | Get job details |
| `POST /api/jobs/{id}/cancel` | `/api/jobs/{id}/cancel` | Cancel a job |
| `GET /api/health` | `/health` | Health check |

## UI Design

- **Theme:** Dark mode with deep space background
- **Colors:** Neon blue (#3b82f6) and purple (#8b5cf6) accents
- **Effects:** Glassmorphism, blur, subtle gradients
- **Fonts:** Inter (UI) + JetBrains Mono (code)
- **Framework:** Tailwind CSS via CDN

## Development

The app uses:
- **FastAPI** - Web framework
- **Jinja2** - Template engine
- **httpx** - Async HTTP client for API proxy
- **Tailwind CSS** - Styling (CDN)

## License

ENSAM Rabat Cloud Computing Project © 2025








