from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import uvicorn

# Import configurations and database
from app.config import settings
from app.services.database import connect_to_mongo, close_mongo_connection

# Import routers
from app.routers import auth, users, chat

# Import middleware
from app.middleware import JWTMiddleware, LoggingMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting FastAPI application...")
    try:
        await connect_to_mongo()
        logger.info("Database connection established")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down FastAPI application...")
    await close_mongo_connection()

# Initialize FastAPI app
app = FastAPI(
    title="FastAPI JWT Auth System",
    description="A comprehensive authentication system with JWT tokens and MongoDB",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add custom middleware
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    JWTMiddleware, 
    protected_paths=["/users", "/admin", "/protected"]
)

# Include routers with JWT protection
app.include_router(auth.router)
app.include_router(users.router, dependencies=[])
app.include_router(chat.router, dependencies=[])

# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "message": "FastAPI JWT Auth System is running",
        "version": "1.0.0"
    }

# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to FastAPI JWT Auth System",
        "docs": "/docs",
        "redoc": "/redoc"
    }

# Protected endpoint example
@app.get("/protected", tags=["Protected"])
async def protected_route():
    """Example protected route that requires JWT authentication"""
    return {
        "message": "This is a protected route",
        "access": "granted"
    }

# Admin endpoint example
@app.get("/admin", tags=["Admin"])
async def admin_route():
    """Example admin route that requires JWT authentication"""
    return {
        "message": "This is an admin route",
        "access": "admin_granted"
    }

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Global exception: {exc}")
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error"
    )

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level="info" if settings.debug else "warning"
    )