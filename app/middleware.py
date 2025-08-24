from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import time
from typing import Callable
from app.auth.jwt_handler import jwt_handler

logger = logging.getLogger(__name__)

class JWTMiddleware(BaseHTTPMiddleware):
    """Middleware for JWT token validation on protected routes"""
    
    def __init__(self, app, protected_paths: list = None):
        super().__init__(app)
        # Define which paths require JWT authentication
        self.protected_paths = protected_paths or [
            "/users",
            "/admin",
            "/protected",
            "/chat"  # Add chat endpoints to protected paths
        ]
        # Paths that should be excluded from JWT validation
        self.excluded_paths = [
            "/auth/token",
            "/auth/register",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health"
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path
        
        # Skip JWT validation for excluded paths
        if any(path.startswith(excluded) for excluded in self.excluded_paths):
            return await call_next(request)
        
        # Skip JWT validation for non-protected paths
        if not any(path.startswith(protected) for protected in self.protected_paths):
            return await call_next(request)
        
        # Extract JWT token from Authorization header
        authorization = request.headers.get("Authorization")
        
        if not authorization or not authorization.startswith("Bearer "):
            return Response(
                content='{"detail":"Missing or invalid authorization header"}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        token = authorization.split(" ")[1]
        
        try:
            # Verify the token
            payload = jwt_handler.verify_token(token)
            
            # Add user info to request state for use in route handlers
            request.state.user = {"username": payload.get("sub")}
            request.state.token_payload = payload
            
        except HTTPException as e:
            return Response(
                content=f'{{"detail":"{e.detail}"}}',
                status_code=e.status_code,
                media_type="application/json",
                headers=e.headers or {}
            )
        except Exception as e:
            logger.error(f"JWT middleware error: {e}")
            return Response(
                content='{"detail":"Authentication failed"}',
                status_code=status.HTTP_401_UNAUTHORIZED,
                media_type="application/json",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        return await call_next(request)

class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for request/response logging"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        # Log request
        logger.info(f"Request: {request.method} {request.url.path}")
        
        # Process request
        response = await call_next(request)
        
        # Calculate processing time
        process_time = time.time() - start_time
        
        # Log response
        logger.info(
            f"Response: {response.status_code} | "
            f"Time: {process_time:.4f}s | "
            f"Path: {request.url.path}"
        )
        
        # Add processing time to response headers
        response.headers["X-Process-Time"] = str(process_time)
        
        return response

class CORSMiddleware(BaseHTTPMiddleware):
    """Custom CORS middleware"""
    
    def __init__(self, app, allowed_origins: list = None, allowed_methods: list = None):
        super().__init__(app)
        self.allowed_origins = allowed_origins or ["*"]
        self.allowed_methods = allowed_methods or ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Handle preflight requests
        if request.method == "OPTIONS":
            response = Response()
        else:
            response = await call_next(request)
        
        # Add CORS headers
        origin = request.headers.get("origin")
        if origin in self.allowed_origins or "*" in self.allowed_origins:
            response.headers["Access-Control-Allow-Origin"] = origin or "*"
        
        response.headers["Access-Control-Allow-Methods"] = ", ".join(self.allowed_methods)
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Max-Age"] = "86400"
        
        return response