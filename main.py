import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

from routers.resume import router as resume_router
from routers.interview import router as interview_router
from routers.coding import router as coding_router

app = FastAPI(
    title="MIT Interview Bot AI Engine",
    description="Zero-latency dynamic voice technical interview system built using FastAPI, Groq LLM, and VAPI.",
    version="1.0.0"
)

# Set up CORS middleware to allow connection from the Next.js frontend or direct clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins (e.g. localhost:3000, 3001, etc.)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods (GET, POST, OPTIONS, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Mount static directory for the web frontend
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
react_dist = os.path.join("frontend", "dist")
react_assets = os.path.join(react_dist, "assets")
if os.path.isdir(react_assets):
    app.mount("/assets", StaticFiles(directory=react_assets), name="react-assets")

# Register routers
app.include_router(resume_router, prefix="/resume", tags=["Resume"])
app.include_router(interview_router, prefix="/interview", tags=["Interview"])
app.include_router(coding_router, prefix="/coding-api", tags=["Coding Studio"])

@app.get("/coding", include_in_schema=False)
async def serve_coding_studio():
    html_file = os.path.join("static", "coding-studio.html")
    if os.path.exists(html_file):
        return FileResponse(html_file, headers={"Cache-Control": "no-store, max-age=0"})
    return HTMLResponse("<h3>Coding studio frontend not found.</h3>")

@app.get("/app", include_in_schema=False)
async def serve_frontend():
    """
    Serves the modern MIT Interview Bot Web Studio single-page application.
    """
    html_file = os.path.join(react_dist, "index.html")
    if not os.path.exists(html_file):
        html_file = os.path.join("static", "index.html")
    if os.path.exists(html_file):
        return FileResponse(html_file, headers={"Cache-Control": "no-store, max-age=0"})
    return HTMLResponse("<h3>Frontend not found in static/index.html</h3>")

@app.get("/", tags=["Health"])
async def root(request: Request = None):
    """
    Base health check endpoint.
    Serves the interactive frontend when accessed from a web browser.
    """
    if request:
        accept = request.headers.get("accept", "")
        # If opened in a web browser, serve the interactive web studio
        if "text/html" in accept and not accept.startswith("*/*"):
            html_file = os.path.join(react_dist, "index.html")
            if not os.path.exists(html_file):
                html_file = os.path.join("static", "index.html")
            if os.path.exists(html_file):
                return FileResponse(html_file, headers={"Cache-Control": "no-store, max-age=0"})
    return {
        "status": "ok",
        "service": "ai-engine"
    }

@app.post("/", tags=["Health"])
async def root_post():
    """
    Catch-all POST for VAPI webhooks sent to the root path.
    """
    print("\n[WARNING] Received a POST request at the root path (/).")
    print("          It looks like VAPI is sending webhooks to the wrong URL.")
    print("          Please update your VAPI Assistant Server URL to append '/interview/transcript'")
    print("          e.g., https://your-ngrok-url.ngrok-free.app/interview/transcript\n")
    return {
        "success": False,
        "data": None,
        "error": "Webhooks must be sent to /interview/transcript, not the root path (/)."
    }

if __name__ == "__main__":
    import uvicorn
    # Start the server on port 8000 (0.0.0.0 allows access from VM host machine)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
