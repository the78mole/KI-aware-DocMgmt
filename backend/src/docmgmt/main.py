from fastapi import FastAPI

app = FastAPI(title="KI-aware-DocMgmt")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
