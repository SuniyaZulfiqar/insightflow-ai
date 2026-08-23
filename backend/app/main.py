from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.workspaces import router as workspaces_router
from app.routers.datasets import router as datasets_router


app = FastAPI(
    title="InsightFlow AI",
    description="AI-powered business intelligence and analytics platform",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(workspaces_router)
app.include_router(datasets_router)


@app.get("/")
def root():
    return {
        "message": "InsightFlow AI API is running!"
    }