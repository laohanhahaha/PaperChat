"""用户认证路由

提供用户注册、登录、登出、获取当前用户信息等接口
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserResponse, Token
from app.services.auth_service import auth_service, get_current_user
from app.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


class UserUpdateRequest(BaseModel):
    """用户信息更新请求"""
    email: Optional[EmailStr] = None
    avatar: Optional[str] = None


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    用户注册
    
    请求体:
        - username: 用户名
        - email: 邮箱
        - password: 密码
    
    返回:
        - 用户信息
    """
    # 检查用户名是否已存在
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名已存在"
        )
    
    # 检查邮箱是否已存在
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮箱已被注册"
        )
    
    # 创建新用户
    hashed_password = auth_service.get_password_hash(user_data.password)
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hashed_password
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user


@router.post("/login", response_model=Token)
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """
    用户登录
    
    请求体:
        - username: 用户名或邮箱
        - password: 密码
    
    返回:
        - JWT Token 及过期时间
    """
    # 查找用户（支持用户名或邮箱登录）
    result = await db.execute(
        select(User).where(
            or_(
                User.username == login_data.username,
                User.email == login_data.username
            )
        )
    )
    user = result.scalar_one_or_none()
    
    # 验证用户存在且密码正确
    if not user or not auth_service.verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户已被禁用",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 生成 JWT Token
    access_token = auth_service.create_access_token(
        data={"sub": str(user.id)}
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """
    用户登出
    
    返回:
        - 登出成功消息
    """
    # 注意：JWT 是无状态的，客户端删除 token 即可完成登出
    # 如果需要实现 token 黑名单，需要额外的存储机制
    return {"message": "登出成功"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    获取当前登录用户信息
    
    需要 JWT Token 认证
    
    返回:
        - 当前用户信息
    """
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_me(
    update_data: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    更新当前用户信息
    
    请求体:
        - avatar: 头像 URL（可选）
        - email: 邮箱（可选）
    
    返回:
        - 更新后的用户信息
    """
    # 检查邮箱是否被其他用户使用
    if update_data.email and update_data.email != current_user.email:
        result = await db.execute(
            select(User).where(
                User.email == update_data.email,
                User.id != current_user.id
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被其他用户使用"
            )
        current_user.email = update_data.email
    
    # 更新头像
    if update_data.avatar is not None:
        current_user.avatar = update_data.avatar
    
    await db.commit()
    await db.refresh(current_user)
    
    return current_user
