from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.meta import router as meta_router

router = APIRouter(prefix="/api/v1", tags=["api-v1"])
router.include_router(meta_router)
router.include_router(auth_router)
