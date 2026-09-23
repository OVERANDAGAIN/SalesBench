from fastapi import FastAPI

app = FastAPI(
    title="SalesBench process health",
    version="0.1.0",
    description="Process responsiveness only; no database or identity readiness claim.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "scope": "api_process"}
