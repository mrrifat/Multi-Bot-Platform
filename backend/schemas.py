from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# User Schemas
class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# BotEnvVar Schemas
class BotEnvVarBase(BaseModel):
    key: str
    value: str


class BotEnvVarCreate(BotEnvVarBase):
    pass


class BotEnvVar(BotEnvVarBase):
    id: int
    bot_id: int

    class Config:
        from_attributes = True


# Deployment Schemas
class DeploymentBase(BaseModel):
    status: str
    log: Optional[str] = None


class Deployment(DeploymentBase):
    id: int
    bot_id: int
    created_at: datetime

    class Config:
        from_attributes = True


# BotApp Schemas
class BotAppBase(BaseModel):
    name: str
    repo_url: Optional[str] = None
    runtime: str = "python"
    start_command: str = "python bot.py"


class BotAppCreate(BotAppBase):
    pass


class BotAppUpdate(BaseModel):
    name: Optional[str] = None
    repo_url: Optional[str] = None
    runtime: Optional[str] = None
    start_command: Optional[str] = None


class BotApp(BotAppBase):
    id: int
    code_path: str
    created_at: datetime
    updated_at: datetime
    env_vars: List[BotEnvVar] = []
    deployments: List[Deployment] = []

    class Config:
        from_attributes = True


# Login Schema
class LoginRequest(BaseModel):
    email: EmailStr
    password: str
