from fastapi import APIRouter, HTTPException, Depends, status
from app.auth.auth_utils import get_current_user, get_current_admin_user
from app.services.database import get_all_users, delete_user, get_user_by_username
from app.models.schemas import UserResponse, APIResponse, UserList
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["Users"])

@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """Get current user profile"""
    try:
        return UserResponse(**current_user)
    except Exception as e:
        logger.error(f"Error getting user profile for '{current_user.get('username')}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user profile"
        )

@router.get("/", response_model=UserList)
async def get_users_list(
    current_user: dict = Depends(get_current_admin_user),
    skip: int = 0,
    limit: int = 100
):
    """Get all users (Admin only)"""
    try:
        users = await get_all_users()
        
        # Apply pagination
        paginated_users = users[skip:skip + limit]
        
        user_responses = [UserResponse(**user) for user in paginated_users]
        
        return UserList(
            users=user_responses,
            total=len(users)
        )
        
    except Exception as e:
        logger.error(f"Error getting users list: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get users list"
        )

@router.get("/{username}", response_model=UserResponse)
async def get_user_by_username_endpoint(
    username: str,
    current_user: dict = Depends(get_current_admin_user)
):
    """Get specific user by username (Admin only)"""
    try:
        user = await get_user_by_username(username)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{username}' not found"
            )
        
        # Remove password field
        user_safe = {k: v for k, v in user.items() if k != "password"}
        return UserResponse(**user_safe)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user '{username}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user"
        )

@router.delete("/me", response_model=APIResponse)
async def delete_current_user(current_user: dict = Depends(get_current_user)):
    """Delete current user account"""
    try:
        success = await delete_user(current_user["username"])
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete user account"
            )
        
        logger.info(f"User account deleted: {current_user['username']}")
        return APIResponse(message="User account deleted successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user '{current_user['username']}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user account"
        )

@router.delete("/{username}", response_model=APIResponse)
async def delete_user_by_username(
    username: str,
    current_user: dict = Depends(get_current_admin_user)
):
    """Delete user by username (Admin only)"""
    try:
        # Check if user exists
        user = await get_user_by_username(username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{username}' not found"
            )
        
        # Prevent admin from deleting themselves via this endpoint
        if username == current_user["username"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account via this endpoint. Use /users/me instead."
            )
        
        success = await delete_user(username)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete user"
            )
        
        logger.info(f"User '{username}' deleted by admin: {current_user['username']}")
        return APIResponse(message=f"User '{username}' deleted successfully")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user '{username}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete user"
        )