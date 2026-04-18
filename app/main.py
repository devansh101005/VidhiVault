# app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router


# Create FastAPI app instance
app = FastAPI(
    title="Adhivakta.AI",
    version="0.1.0"
)



app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins (only for dev)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------
# Routers
# ---------------------------
app.include_router(health_router)