import app.ssl_compat  # noqa: F401
import logging
from datetime import datetime, timezone
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.config import settings

logger = logging.getLogger(__name__)

# Enable MLflow LLM tracing once, at import. Best-effort: an unreachable tracking server
# must not stop the API from starting, and tracing is telemetry rather than a
# precondition for generating code.
try:
    from app.cost.mlflow_sink import enable_tracing

    if enable_tracing():
        logger.info("MLflow LLM tracing enabled; model calls will appear under Traces")
except Exception as _tracing_exc:  # noqa: BLE001
    logger.warning("MLflow LLM tracing unavailable: %s", _tracing_exc)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Microservice Code Studio - Autonomous Java 21 / Spring Boot 3.x Generator",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS for the React frontend and local clients.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.services.auth_service import router as auth_router, authenticated_user
app.include_router(auth_router, prefix="/api/v1")

@app.middleware("http")
async def require_authentication(request: Request, call_next):
    if request.url.path.startswith("/api/v1/") and request.method != "OPTIONS":
        public = {"/api/v1/auth/login", "/api/v1/auth/mvp", "/api/v1/auth/session", "/api/v1/auth/logout"}
        if request.url.path not in public:
            user = authenticated_user(request)
            if user is None:
                return JSONResponse(status_code=401, content={"detail": "Authentication required"})
            request.state.user = user
    session_id = request.headers.get("X-Session-ID")
    guided = request.method == "POST" and request.url.path.startswith(("/api/v1/requirements/", "/api/v1/architecture/", "/api/v1/models/"))
    if session_id and guided:
        from app.services.workspace_guard import get_validated_workspace_path
        from app.cost.recording import recording_context
        from fastapi import HTTPException
        try:
            get_validated_workspace_path(session_id, require_exists=True)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        with recording_context(session_id, "GUIDED_" + request.url.path.rsplit("/", 1)[-1].upper()):
            response = await call_next(request)
        from app.models.session import SessionLocal, GenerationSessionDB
        from app.api.routes_session import _record_session_cost
        db = SessionLocal()
        try:
            row = db.get(GenerationSessionDB, session_id)
            if row:
                _record_session_cost(session_id, row.status.value, db_sess=row, db=db)
        finally:
            db.close()
        return response
    return await call_next(request)

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
    # Log the traceback. A handler that returns a tidy envelope while printing nothing
    # leaves an operator with a 500 and no way to find out why -- which is exactly what
    # happened when DeepSeek rejected `response_format`: eight 500s in the access log,
    # not one line saying what failed, so the cause had to be reproduced by hand from
    # outside the running server. The client gets the summary; the server keeps the stack.
    #
    # The logging is itself wrapped: an error handler that raises while reporting an
    # error replaces a diagnosable 500 with an undiagnosable one.
    try:
        logger.exception(
            "unhandled error on %s %s: %s",
            getattr(request, "method", "?"),
            getattr(getattr(request, "url", None), "path", "?"),
            exc,
        )
    except Exception:  # noqa: BLE001 -- never let logging mask the original failure
        pass
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
    """Health, plus whether the telemetry mirror and LLM tracing are actually on.

    The tracing state is reported here because its absence is otherwise invisible: the
    tracking UI showed an empty Traces page and nothing anywhere said why. Runs and traces
    are two different features -- this module mirrors cost records as RUNS, and a trace is a
    span tree that requires instrumenting the calls -- so "no traces" looked like a broken
    mirror when it was a missing feature. Now the answer is one request.
    """
    telemetry: dict = {"tracing": False, "failures": []}
    try:
        from app.cost.mlflow_sink import mirror_failures, tracing_enabled

        telemetry = {"tracing": tracing_enabled(), "failures": mirror_failures()[-3:]}
    except Exception as exc:  # noqa: BLE001 - health must answer even if telemetry cannot
        telemetry = {"tracing": False, "failures": [f"{type(exc).__name__}: {exc}"]}

    return {
        "status": "UP",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "dockerEnabled": settings.DOCKER_ENABLED,
        "mlflow": telemetry
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


