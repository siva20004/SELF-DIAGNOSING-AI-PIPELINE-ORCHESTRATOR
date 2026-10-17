import os
import time

# Enforce Indian Standard Time (IST) on POSIX/Linux containers (Render, Vercel, Docker)
if hasattr(time, "tzset"):
    os.environ["TZ"] = "Asia/Kolkata"
    try:
        time.tzset()
    except Exception:
        pass

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database.session import init_db
from app.api.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup with retry logic for cloud/serverless DBs like Neon
    try:
        init_db()
        print("INFO: Database tables verified and initialized successfully.")
    except Exception as e:
        print(f"WARNING: Initial DB connection failed ({e}). Retrying in 2 seconds...")
        import time
        time.sleep(2)
        try:
            init_db()
            print("INFO: Database tables initialized successfully on retry.")
        except Exception as retry_err:
            print(f"ERROR: Database initialization retry failed: {retry_err}")
    yield


app = FastAPI(
    title="Self-Diagnosing AI Pipeline Orchestrator",
    description="Real Data Pipeline Orchestrator with Data Contracts, Quality Validation, and PostgreSQL Storage",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.responses import JSONResponse
from fastapi import Request

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    traceback.print_exc()
    origin = request.headers.get("origin", "*")
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {str(exc)}"},
        headers={
            "Access-Control-Allow-Origin": origin if origin != "*" else "*",
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Allow-Methods": "*",
        }
    )

app.include_router(router)


@app.get("/")
def root():
    return {
        "system": "Self-Diagnosing AI Pipeline Orchestrator",
        "status": "ONLINE",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
def health():
    return {"status": "HEALTHY"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
