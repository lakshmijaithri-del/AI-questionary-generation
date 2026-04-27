# main.py (Unified Version)
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from api.endpoints import router as api_router
from config import OLLAMA_MODEL

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("INFO:     LMS Questionary Engine Started.")
    print(f"INFO:     Primary Generation Model: {OLLAMA_MODEL}")
    yield
    print("INFO:     Shutting down.")

app = FastAPI(title="LMS Questionary API", lifespan=lifespan)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8501, reload=True)