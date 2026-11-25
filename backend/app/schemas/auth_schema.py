from typing import Annotated

from pydantic import BaseModel, Field

from app.models.role_enum import RoleEnum

username_str = Annotated[str, Field(..., min_length=3, max_length=50)]
# Lower bound shared by every role; AuthService.validate_credentials applies
# the stricter per-role minimum.
password_str = Annotated[str, Field(..., min_length=4, max_length=50)]


class LoginRequest(BaseModel):
    username: username_str
    password: password_str


class ResetPasswordRequest(BaseModel):
    account_id: int


class PasswordChangeResponse(BaseModel):
    message: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    new_password: password_str
    old_password: password_str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: RoleEnum
    first_login: bool
