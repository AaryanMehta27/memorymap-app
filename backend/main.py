from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import vision, query, floorplan
import os

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


@app.get("/health")
def health():
    return {"status": "ok"}
