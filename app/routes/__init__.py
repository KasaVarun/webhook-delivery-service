from fastapi import APIRouter

from app.routes.deliveries import router as deliveries_router
from app.routes.events import router as events_router
from app.routes.health import router as health_router
from app.routes.metrics import router as metrics_router
from app.routes.webhooks import router as webhooks_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(webhooks_router)
api_router.include_router(events_router)
api_router.include_router(deliveries_router)
api_router.include_router(metrics_router)