from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta, datetime
from app.auth.jwt_handler import jwt_handler
from app.auth import auth_utils
from app.services.database import create_user, update_user_password
from app.models.schemas import UserCreate, Token, APIResponse, PasswordChange
from app.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/register", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate):
    """Register a new user"""
    try:
        # Validate password strength
        auth_utils.auth_utils.validate_password_strength(user.password)
        
        # Hash the password
        hashed_password = auth_utils.auth_utils.get_password_hash(user.password)
        
        # Prepare user data
        user_data = {
            "username": user.username,
            "password": hashed_password,
            "is_admin": user.is_admin,  # Add admin flag
            "created_at": datetime.utcnow(),
            "is_active": True,
            "last_login": None
        }
        
        # Create user in database
        user_id = await create_user(user_data)
        
        logger.info(f"New user registered: {user.username}")
        return APIResponse(
            message="User registered successfully",
            data={"user_id": str(user_id), "username": user.username}
        )
        
    except ValueError as e:
        logger.warning(f"Registration failed for '{user.username}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error for '{user.username}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Login user and return JWT token"""
    try:
        # Authenticate user
        user = await auth_utils.auth_utils.authenticate_user(form_data.username, form_data.password)
        
        if not user:
            logger.warning(f"Login failed for user: {form_data.username}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
        access_token = jwt_handler.create_access_token(
            data={"sub": user["username"]},
            expires_delta=access_token_expires
        )
        
        # Update last login time (optional)
        # You can add this functionality to track user login times
        
        logger.info(f"User logged in successfully: {form_data.username}")
        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60  # Convert to seconds
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error for '{form_data.username}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@router.post("/refresh", response_model=Token)
async def refresh_token(current_token: str = Depends(auth_utils.oauth2_scheme)):
    """Refresh JWT token"""
    try:
        new_token = jwt_handler.refresh_token(current_token)
        
        return Token(
            access_token=new_token,
            token_type="bearer",
            expires_in=settings.access_token_expire_minutes * 60
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )
from app.services.database import get_user_by_username
@router.post("/change-password", response_model=APIResponse)
async def change_password(
    password_data: PasswordChange,
    current_user: dict = Depends(auth_utils.get_current_user)
):
    """Change user password"""
    try:
        # Verify current password
        user_with_password = await get_user_by_username(current_user["username"])
        if not auth_utils.auth_utils.verify_password(password_data.current_password, user_with_password["password"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Validate new password strength
        auth_utils.AuthUtils.validate_password_strength(password_data.new_password)
        
        # Hash new password
        new_hashed_password = auth_utils.AuthUtils.get_password_hash(password_data.new_password)
        
        # Update password in database
        success = await update_user_password(current_user["username"], new_hashed_password)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password"
            )
        
        logger.info(f"Password changed successfully for user: {current_user['username']}")
        return APIResponse(message="Password updated successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change error for '{current_user['username']}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )