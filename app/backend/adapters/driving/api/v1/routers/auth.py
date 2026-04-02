"""
Auth Router - Authentication and User Management

Handles:
- Login (JWT token generation)
- User info retrieval
- User CRUD (admin only)
- Password management

Hexagonal Architecture:
- Driving adapter (REST API)
- Uses database.py (legacy, to be migrated to UserRepository in future)
"""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Depends
import logging

from auth import create_user_token
from database import db
from middleware import get_current_user, require_admin, CurrentUser
from adapters.driving.api.v1.schemas.auth_schemas import (
    LoginRequest,
    LoginResponse,
    UserInfo,
    UserCreate,
    UserUpdate,
    PasswordChange,
    UserListResponse,
    MessageResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    User login - returns JWT token

    Default credentials:
    - Admin: username=admin, password=<from logs or ADMIN_DEFAULT_PASSWORD env var>
    - Get password: docker compose logs backend | grep "Password:"
    """
    user = db.authenticate_user(request.username, request.password)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password"
        )

    # Create JWT token
    token = create_user_token(user)

    logger.info(f"✅ Login successful: {user['username']} (role: {user['role']})")

    # Convert datetime objects to strings for response
    created_at = user["created_at"]
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat()
    
    last_login = user.get("last_login")
    if isinstance(last_login, datetime):
        last_login = last_login.isoformat()

    return LoginResponse(
        access_token=token,
        user=UserInfo(
            id=user["id"],
            username=user["username"],
            email=user["email"],
            role=user["role"],
            created_at=created_at,
            last_login=last_login
        )
    )


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(current_user: CurrentUser = Depends(get_current_user)):
    """Get current user information"""
    user = db.get_user_by_id(current_user.user_id)

    # Convert datetime objects to strings
    created_at = user["created_at"]
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat()
    
    last_login = user.get("last_login")
    if isinstance(last_login, datetime):
        last_login = last_login.isoformat()

    return UserInfo(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        role=user["role"],
        created_at=created_at,
        last_login=last_login
    )


@router.get("/users", response_model=UserListResponse)
async def list_users(current_user: CurrentUser = Depends(require_admin)):
    """List all users (ADMIN only)"""
    users = db.list_users()

    user_list = []
    for u in users:
        # Convert datetime objects to strings
        created_at = u["created_at"]
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        
        last_login = u.get("last_login")
        if last_login and isinstance(last_login, datetime):
            last_login = last_login.isoformat()
        
        user_list.append(UserInfo(
            id=u["id"],
            username=u["username"],
            email=u["email"],
            role=u["role"],
            created_at=created_at,
            last_login=last_login
        ))

    return UserListResponse(
        users=user_list,
        total=len(user_list)
    )


@router.post("/users", response_model=UserInfo)
async def create_user(
    user_data: UserCreate,
    current_user: CurrentUser = Depends(require_admin)
):
    """Create new user (ADMIN only)"""
    user_id = db.create_user(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password,
        role=user_data.role
    )

    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="User creation error (username or email already exists)"
        )

    user = db.get_user_by_id(user_id)

    # Convert datetime objects to strings
    created_at = user["created_at"]
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat()
    
    last_login = user.get("last_login")
    if isinstance(last_login, datetime):
        last_login = last_login.isoformat()

    return UserInfo(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        role=user["role"],
        created_at=created_at,
        last_login=last_login
    )


@router.put("/users/{user_id}", response_model=MessageResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: CurrentUser = Depends(require_admin)
):
    """Update user (ADMIN only)"""
    if user_data.role:
        success = db.update_user_role(user_id, user_data.role)
        if not success:
            raise HTTPException(status_code=404, detail="User not found")

    return MessageResponse(message=f"User {user_id} updated")


@router.delete("/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int,
    current_user: CurrentUser = Depends(require_admin)
):
    """Delete user (ADMIN only)"""
    # Don't allow self-deletion
    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=400,
            detail="You cannot delete your own account"
        )

    success = db.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")

    return MessageResponse(message=f"User {user_id} deleted")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    request: PasswordChange,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Change current user's password"""
    user = db.get_user_by_id(current_user.user_id)

    # Verify old password
    if not db.verify_password(request.old_password, user["password_hash"]):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect"
        )

    # Change password
    success = db.change_password(current_user.user_id, request.new_password)

    if not success:
        raise HTTPException(status_code=500, detail="Password change error")

    logger.info(f"✅ Password changed for user: {current_user.username}")

    return MessageResponse(message="Password changed successfully")
