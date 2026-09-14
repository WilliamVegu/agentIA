from datetime import datetime, timezone
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.config import settings

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Microservice Code Studio - Autonomous Java 21 / Spring Boot 3.x Generator",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS for Streamlit frontend and local clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Centralized Error Handlers (Constitution Principle III)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": 400,
            "message": "Validation error in specification payload",
            "details": [f"{err['loc']}: {err['msg']}" for err in exc.errors()]
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": 500,
            "message": "Internal server error occurred",
            "details": [str(exc)]
        }
    )

@app.get("/healthz", tags=["Health"])
async def healthcheck():
    return {
        "status": "UP",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }

# Include routers dynamically when available
try:
    from app.api.routes_spec import router as spec_router
    app.include_router(spec_router, prefix="/api/v1")
except ImportError:
    pass

try:
    from app.api.routes_session import router as session_router
    app.include_router(session_router, prefix="/api/v1")
except ImportError:
    pass

try:
    from app.api.routes_artifact import router as artifact_router
    app.include_router(artifact_router, prefix="/api/v1")
except ImportError:
    pass

try:
    from app.api.routes_publish import router as publish_router
    app.include_router(publish_router, prefix="/api/v1")
except ImportError:
    pass

try:
    from app.api.routes_requirements import router as requirements_router
    app.include_router(requirements_router, prefix="/api/v1")
except ImportError:
    pass

try:
    from app.api.routes_architecture import router as architecture_router
    app.include_router(architecture_router, prefix="/api/v1")
except ImportError:
    pass

try:
    from app.api.routes_models_sql import router as models_sql_router
    app.include_router(models_sql_router, prefix="/api/v1")
except ImportError:
    pass

try:
    from app.api.routes_tests import router as tests_router
    app.include_router(tests_router)
except ImportError:
    pass

try:
    from app.api.routes_security import router as security_router
    app.include_router(security_router, prefix="/api/v1")
except ImportError:
    pass

try:
    from app.api.routes_devops import router as devops_router
    app.include_router(devops_router, prefix="/api/v1")
except ImportError:
    pass

try:
    from app.api.routes_orchestrator import router as orchestrator_router
    app.include_router(orchestrator_router, prefix="/api/v1")
except ImportError:
    pass

try:
    from app.api.routes_llm import router as llm_router
    app.include_router(llm_router, prefix="/api/v1")
except ImportError:
    pass


