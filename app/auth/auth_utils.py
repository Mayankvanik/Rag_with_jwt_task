from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from app.services.database import get_user_by_username
from .jwt_handler import jwt_handler
import logging

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

class AuthUtils:
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Generate password hash"""
        return pwd_context.hash(password)

    @staticmethod
    async def authenticate_user(username: str, password: str) -> dict:
        """Authenticate user credentials"""
        try:
            user = await get_user_by_username(username)
            if not user:
                logger.warning(f"Authentication failed: User '{username}' not found")
                return False
            
            if not AuthUtils.verify_password(password, user["password"]):
                logger.warning(f"Authentication failed: Invalid password for user '{username}'")
                return False
            
            logger.info(f"User '{username}' authenticated successfully")
            return user
            
        except Exception as e:
            logger.error(f"Authentication error for user '{username}': {e}")
            return False

    @staticmethod
    def validate_password_strength(password: str) -> bool:
        """Validate password meets minimum requirements"""
        if len(password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long"
            )
        return True

# Dependency to get current user from JWT token
async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Get current authenticated user from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Verify and decode the token
        payload = jwt_handler.verify_token(token)
        username: str = payload.get("sub")
        
        if username is None:
            raise credentials_exception
        
        # Get user from app.services.database
        user = await get_user_by_username(username)
        if user is None:
            logger.warning(f"User '{username}' not found in database")
            raise credentials_exception
        
        # Remove password from user data before returning
        user_safe = {k: v for k, v in user.items() if k != "password"}
        return user_safe
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        raise credentials_exception

# Dependency for admin users only
async def get_current_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    """Get current user if they are an admin"""
    if current_user.get("username") != "admin" and not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions. Admin access required."
        )
    return current_user

# Create auth utils instance
auth_utils = AuthUtils()