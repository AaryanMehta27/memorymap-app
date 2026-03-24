import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import vision, query, floorplan, alerts

app = FastAPI(title="MemoryMap AI Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vision.router, prefix="/api/vision")
app.include_router(query.router, prefix="/api/query")
app.include_router(floorplan.router, prefix="/api/floorplan")
app.include_router(alerts.router, prefix="/api/alerts")


@app.get("/health")
def health():
    return {"status": "ok"}
