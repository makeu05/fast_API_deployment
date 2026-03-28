from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.router import router
import os

app = FastAPI(
    title="Module G – Hypothèses & Méthodologies Techniques",
    description=(
        "Module G du projet intégrateur d'investigation numérique. "
        "Génère des hypothèses forensiques et un plan méthodologique "
        "à partir des incohérences détectées dans les PV d'audition."
    ),
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root():
    return {
        "module": "G",
        "description": "Hypothèses & Méthodologies Techniques",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8006))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)

