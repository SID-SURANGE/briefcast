from fastapi import FastAPI

app = FastAPI(title="briefcast")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    pass
