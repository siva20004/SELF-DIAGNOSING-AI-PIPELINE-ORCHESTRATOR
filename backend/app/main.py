import os
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
