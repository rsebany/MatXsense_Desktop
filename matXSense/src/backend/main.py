"""MatXSense FastAPI application: auth + API + static frontend."""
from pathlib import Path

from fastapi import Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm

from .auth import authenticate_user, create_access_token
from .api import router as api_router

from fastapi import FastAPI

app = FastAPI(
    title="MatXSense API",
    description="Material Degradation Monitoring — sensors, bridge ML (LightGBM RUL, RF Health), health dashboard",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/auth/login")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login: returns JWT. Demo: admin/demo, password: demo123."""
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_access_token({"sub": user["username"]})
    return {"access_token": token, "token_type": "bearer", "username": user["username"]}

@app.post("/auth/register")
def register():
    raise HTTPException(status_code=501, detail="Use demo login: admin / demo123")

app.include_router(api_router)

FRONTEND_DIR = Path(__file__).resolve().parents[2] / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/")
def index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "MatXSense API", "docs": "/docs", "login": "POST /auth/login"}
