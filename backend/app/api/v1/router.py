from fastapi import APIRouter

from app.api.v1.endpoints.todos import router as todos_router

router = APIRouter()
router.include_router(todos_router)
