from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from dotenv import load_dotenv
import logging
import time

from app.db.database import init_db
from app.routes import agents, ask, upload

# -----------------------------
# Load env
# -----------------------------
load_dotenv()

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    force=True
)

logger = logging.getLogger(__name__)

# -----------------------------
# App Init
# -----------------------------
app = FastAPI()

# -----------------------------
# Init DB
# -----------------------------
init_db()

# -----------------------------
# CORS Middleware
# -----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Custom Middleware (Logging)
# -----------------------------
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    response = await call_next(request)

    duration = round(time.time() - start_time, 3)

    logger.info(
        f"{request.method} {request.url.path} "
        f"Status: {response.status_code} "
        f"Time: {duration}s"
    )

    return response

# -----------------------------
# Validation Error Handler
# -----------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"Validation error: {exc.errors()}")

    return JSONResponse(
        status_code=422,
        content={
            "error": "Invalid request body",
            "details": jsonable_encoder(exc.errors()),
        },
    )

# -----------------------------
# Routes
# -----------------------------
app.include_router(agents.router)
app.include_router(ask.router)
app.include_router(upload.router)

# -----------------------------
# Health Check
# -----------------------------
@app.get("/")
def home():
    return {"message": "Dynamic Multi-Agent System Running"}