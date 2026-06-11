from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.config import settings
from app.database import engine, Base
from app.routers import auth, loss, warning, actions, config, reports
from app.scheduler import start_scheduler, shutdown_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    scheduler = start_scheduler()
    yield
    shutdown_scheduler(scheduler)


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="智慧零售损耗预警后端服务，提供商品损耗评分、临期提醒、盘亏异常、报损提交、门店对比、原因归类和预警订阅等接口",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "type": type(exc).__name__
        }
    )


@app.get("/", tags=["系统"])
def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": "1.0.0",
        "status": "running",
        "api_docs": "/docs",
        "api_prefix": settings.API_V1_STR
    }


@app.get("/health", tags=["系统"])
def health_check():
    return {
        "status": "healthy",
        "timestamp": __import__("datetime").datetime.utcnow().isoformat()
    }


app.include_router(auth.router, prefix=settings.API_V1_STR)
app.include_router(loss.router, prefix=settings.API_V1_STR)
app.include_router(warning.router, prefix=settings.API_V1_STR)
app.include_router(actions.router, prefix=settings.API_V1_STR)
app.include_router(config.router, prefix=settings.API_V1_STR)
app.include_router(reports.router, prefix=settings.API_V1_STR)
