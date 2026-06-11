"""
Copa Agent ⚽ — Backend API Server
FastAPI application that serves the web dashboard and proxies requests
to the Google Cloud Agent Builder agent with GitLab MCP integration.
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

# Load environment variables before importing routes — those modules construct
# AgentService()/GitLabToolExecutor() at import time and read GITLAB_*/GOOGLE_*
# env vars in their constructors, so .env must be loaded first or the live
# token/model config is silently missed.
load_dotenv()

from routes.agent import router as agent_router, agent_svc
from routes.dashboard import router as dashboard_router
from routes.webhooks import router as webhooks_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("copa-agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan handler — runs once at startup and once at shutdown.

    Startup: connect the GitLab MCP server (npx @modelcontextprotocol/server-gitlab)
    so that subsequent tool calls can route through the real MCP protocol.
    If the MCP server fails to start (no Node/npx, network error, bad token) the
    agent degrades gracefully to python-gitlab for all operations — it never
    crashes.

    Shutdown: cleanly close the stdio subprocess and MCP session.
    """
    # --- startup ---
    try:
        logger.info("Startup: connecting GitLab MCP server…")
        await agent_svc.tools.init_mcp()
        if agent_svc.tools.mcp and agent_svc.tools.mcp.available:
            logger.info("✅ GitLab MCP server ready — agent mode is 'mcp+live'.")
        else:
            logger.info("ℹ️  GitLab MCP server not available — using python-gitlab fallback.")
    except Exception as e:
        logger.warning(f"MCP startup error (non-fatal): {e}")
    yield
    # --- shutdown ---
    try:
        await agent_svc.tools.stop_mcp()
        logger.info("GitLab MCP server disconnected.")
    except Exception:
        pass


# Create FastAPI app
app = FastAPI(
    title="Copa Agent API",
    description="AI DevOps Commander for FIFA World Cup 2026 — powered by Gemini + GitLab MCP",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8080").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(agent_router, prefix="/api/agent", tags=["Agent"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(webhooks_router, prefix="/api/webhooks", tags=["Webhooks"])

# Serve frontend static files
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.exists(frontend_dir):
    app.mount("/css", StaticFiles(directory=os.path.join(frontend_dir, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(frontend_dir, "js")), name="js")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(os.path.join(frontend_dir, "index.html"))

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Copa Agent API",
        "version": "1.0.0"
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=True)
