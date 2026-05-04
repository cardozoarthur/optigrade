from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.routes import (
    academic,
    courses,
    enrollment,
    imports,
    optimization,
    professors,
    rooms,
    students,
    teacher_portal,
    timeslots,
)
from app.core.config import settings
from app.db.session import get_db
from app.services.readiness import build_readiness_report

app = FastAPI(
    title="OptiGrade API",
    version="0.1.0",
    description="API para planejamento e otimizacao de oferta de disciplinas.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_internal_secret(request: Request, call_next):
    secret_required = settings.optigrade_require_internal_secret or bool(
        settings.optigrade_internal_api_secret
    )
    if secret_required and request.url.path != "/health":
        if not settings.optigrade_internal_api_secret:
            return JSONResponse(
                status_code=503,
                content={"detail": "OPTIGRADE_INTERNAL_API_SECRET nao configurado"},
            )
        provided = request.headers.get("x-optigrade-internal-secret")
        if provided != settings.optigrade_internal_api_secret:
            return JSONResponse(
                status_code=403,
                content={"detail": "Canal interno do OptiGrade obrigatorio"},
            )
    return await call_next(request)


app.include_router(courses.router, prefix="/courses", tags=["courses"])
app.include_router(academic.router, tags=["academic"])
app.include_router(professors.router, prefix="/professors", tags=["professors"])
app.include_router(students.router, tags=["students"])
app.include_router(rooms.router, prefix="/rooms", tags=["rooms"])
app.include_router(timeslots.router, prefix="/timeslots", tags=["timeslots"])
app.include_router(imports.router, prefix="/imports", tags=["imports"])
app.include_router(optimization.router, prefix="/optimization", tags=["optimization"])
app.include_router(enrollment.router, prefix="/enrollment", tags=["enrollment"])
app.include_router(teacher_portal.router, prefix="/teacher-portal", tags=["teacher portal"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readiness")
def readiness(semester: str = "2026/2", db: Session = Depends(get_db)) -> dict[str, object]:
    return build_readiness_report(db, semester=semester)
