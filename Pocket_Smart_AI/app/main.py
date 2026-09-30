from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import BASE_DIR, settings
from .database import init_db
from .routes.api import router as api_router
from .routes.pages import router as page_router


@asynccontextmanager
async def lifespan(app: FastAPI):

    init_db()

    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=(
        "PocketSmart AI - "
        "Budget-aware GenAI recommendation assistant"
    ),
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.mount(
    "/static",
    StaticFiles(
        directory=str(BASE_DIR / "app" / "static")
    ),
    name="static",
)


app.include_router(page_router)
app.include_router(api_router)


@app.get("/startup")
def startup_status():

    return {
        "status": "initialized",
        "service": settings.APP_NAME,
    }


@app.get("/health")
def health():

    return {
        "status": "ok",
        "service": settings.APP_NAME,
    }


if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )