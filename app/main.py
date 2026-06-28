from fastapi import FastAPI

from app.routers.forge import router as forge_router

app = FastAPI(title="Agent Forge", version="0.1.0")
app.include_router(forge_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
