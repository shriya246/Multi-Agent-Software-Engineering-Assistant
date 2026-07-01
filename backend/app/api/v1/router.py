from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.meta import router as meta_router
from app.api.v1.repositories import router as repositories_router
from app.api.v1.runs import router as runs_router

router = APIRouter(prefix="/api/v1", tags=["api-v1"])
router.include_router(meta_router)
router.include_router(auth_router)
router.include_router(repositories_router)
router.include_router(runs_router)
