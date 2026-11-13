from fastapi import APIRouter

from app.api.v1 import ats_resume, health, jobs, matching, resumes, sessions

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(sessions.router)
api_router.include_router(resumes.router)
api_router.include_router(jobs.router)
api_router.include_router(matching.router)
api_router.include_router(ats_resume.router)
