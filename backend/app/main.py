from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base

# Import routers directly from route modules
from app.routes.auth import router as auth_router
from app.routes.weather import router as weather_router
from app.routes.districts import router as districts_router
from app.routes.compare import router as compare_router
from app.routes.dashboard import router as dashboard_router
from app.routes.ai import router as ai_router
from app.routes.admin import router as admin_router

app = FastAPI(
    title="INGRES AI API",
    description="API server for INGRES AI - India's Ground Water Resource Estimation System Virtual Assistant",
    version="1.0.0"
)

# Configure CORS Origins list
origins = [org.strip() for org in settings.CORS_ORIGINS.split(",") if org.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(weather_router)
app.include_router(districts_router)
app.include_router(compare_router)
app.include_router(dashboard_router)
app.include_router(ai_router)
app.include_router(admin_router)


@app.get("/")
def read_root():
    return {
        "name": "INGRES AI API",
        "description": "AI-driven Virtual Assistant for India's Ground Water Resource Estimation System",
        "status": "Online",
        "documentation_url": "/docs"
    }
