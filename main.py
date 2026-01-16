from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import auth, students, exams, instructor, debug
from app.core.config import get_settings
import os
import uvicorn
settings = get_settings()

app = FastAPI(
    title="AI Oral Examination System",
    version="2.0.0",
    docs_url="/api/docs"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(students.router)
app.include_router(exams.router)
app.include_router(instructor.router)
app.include_router(debug.router)

@app.get("/")
def root():
    return {
        "message": "AI Oral Examination API",
        "version": "2.0.0",
        "docs": "/api/docs"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "groq_configured": bool(settings.GROQ_API_KEY)
    }

@app.on_event("startup")
async def startup_event():
    print("🚀 AI Oral Examination System Starting...")
    print(f"📚 Documentation: http://localhost:8000/api/docs")
    
    # Create necessary directories
    os.makedirs("results", exist_ok=True)
    os.makedirs("uploads", exist_ok=True)

if __name__ == "__main__":
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )