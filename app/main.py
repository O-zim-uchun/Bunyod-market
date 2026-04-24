from fastapi import FastAPI

app = FastAPI(title="Bunyod Market")


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
