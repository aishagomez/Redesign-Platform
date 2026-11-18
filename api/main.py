from pathlib import Path
from contextlib import asynccontextmanager
import logging
import os
import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base, SessionLocal
from models import User, WorkGroup, GroupMembership, Project, Pipeline, ServiceType, Tool, ToolParameter, ExecutionLog, Notification, StageExecution
from routers import (
    auth_router, projects_router, pipelines_router,
    service_types_router, tools_router, tool_params_router,
    executions_router, orchestration_router, monitoring_router, files_router, manual_router, documentation_router, reports_router, profile_router, groups_router,
)
from import_tool_from_xml import import_tools_from_directory
from services.auth import ensure_bootstrap_admin, ensure_guest_user
from services.guest_cleanup import cleanup_expired_guest_data
from services.orchestration import get_watchdog

logger = logging.getLogger(__name__)
GUEST_CLEANUP_INTERVAL_SECONDS = max(60, int(os.environ.get("GUEST_CLEANUP_INTERVAL_SECONDS", "3600")))


def _guest_cleanup_loop(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        db = SessionLocal()
        try:
            removed = cleanup_expired_guest_data(db)
            if any(removed.values()):
                logger.info("Expired guest data removed: %s", removed)
        except Exception:
            logger.exception("Guest data retention cleanup failed")
            db.rollback()
        finally:
            db.close()
        if stop_event.wait(GUEST_CLEANUP_INTERVAL_SECONDS):
            break


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Crear tablas faltantes sin borrar los datos persistentes.
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        admin_user = ensure_bootstrap_admin(db)
        print(f"[Startup] Bootstrap admin ready: id={admin_user.id}, email={admin_user.email}, role={admin_user.role}")
        guest_user = ensure_guest_user(db)
        print(f"[Startup] Shared guest ready: id={guest_user.id}")
    finally:
        db.close()

    # Importar herramientas declaradas en XML
    definitions_dir = Path(__file__).resolve().parent / "examples"
    imported_tools = import_tools_from_directory(str(definitions_dir))
    print(f"[Startup] XML definitions dir: {definitions_dir}")
    print(f"[Startup] Imported tools from XML: {len(imported_tools)}")
    for tool in imported_tools:
        print(f"[Startup] Tool synced: id={tool.id}, name={tool.name}, version={tool.version}")

    # Arrancar watchdog en thread daemon
    watchdog = get_watchdog(db_factory=SessionLocal)
    watchdog.start()
    cleanup_stop_event = threading.Event()
    cleanup_thread = threading.Thread(
        target=_guest_cleanup_loop,
        args=(cleanup_stop_event,),
        name="guest-data-cleanup",
        daemon=True,
    )
    cleanup_thread.start()

    yield

    cleanup_stop_event.set()
    cleanup_thread.join(timeout=5)
    # Al apagar, detener watchdog
    watchdog.stop()


app = FastAPI(
    title="Pipeline Bioinformático API",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(pipelines_router)
app.include_router(service_types_router)
app.include_router(tools_router)
app.include_router(tool_params_router)
app.include_router(executions_router)
app.include_router(orchestration_router)
app.include_router(monitoring_router)
app.include_router(files_router)
app.include_router(manual_router)
app.include_router(documentation_router)
app.include_router(reports_router)
app.include_router(profile_router)
app.include_router(groups_router)


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "version": "0.3.0"}
