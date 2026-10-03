import pathlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api import acid, cooling, extraction, purification, repackaging, salt, waste

app = FastAPI(title="Nuclear Fuel Recycling Digital Twin API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cooling.router, prefix="/api", tags=["cooling"])
app.include_router(acid.router, prefix="/api", tags=["dissolution-acid"])
app.include_router(salt.router, prefix="/api", tags=["dissolution-salt"])
app.include_router(extraction.router, prefix="/api", tags=["extraction"])
app.include_router(purification.router, prefix="/api", tags=["purification"])
app.include_router(repackaging.router, prefix="/api", tags=["repackaging"])
app.include_router(waste.router, prefix="/api", tags=["waste"])

FRONTEND_DIR = pathlib.Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
