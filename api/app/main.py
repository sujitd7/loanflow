import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .errors import install_error_handlers
from .routers import auth, health

logging.basicConfig(level=settings.log_level)


def create_app() -> FastAPI:
    app = FastAPI(title="LoanFlow API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_error_handlers(app)

    app.include_router(health.router)
    app.include_router(auth.router)
    # Register new routers here as phases land:
    # app.include_router(loan_files.router)
    # app.include_router(tasks.router)
    # app.include_router(dashboard.router)

    return app


app = create_app()
