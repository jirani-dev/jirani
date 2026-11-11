from datetime import UTC, datetime, timedelta
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.config import settings
from app.models import Account, RoleEnum
from app.repositories.auth_repo import AuthRepo
from app.schemas import (
    AccountCreateRequest,
    AccountRead,
    BulkCreateRequest,
    BulkCreateResponse,
    BulkCredentialItem,
)
from app.services.auth_errors import UserNotFound

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self, auth_repo: AuthRepo):
        self.auth_repo = auth_repo

    @staticmethod
    def validate_credentials(
        role: RoleEnum, password: str, context: str = "create"
    ) -> None:
        if context == "reset":
            return
        if context not in ("create", "self_change"):
            raise ValueError("Invalid role or context for password validation.")
        if role == RoleEnum.student:
            if context == "self_change" and len(password) < 4:
                raise ValueError(
                    "Password must be at least 4 characters long for students."
                )
        elif len(password) < 8:
            raise ValueError(
                "Password must be at least 8 characters long for teachers and admins."
            )

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        return bool(pwd_context.verify(plain_password, hashed_password))

    @staticmethod
    def get_password_hash(password: str) -> str:
        hashed: str = pwd_context.hash(password)
        return hashed

    def get_user_by_username(self, username: str) -> Account | None:
        return self.auth_repo.get_by_username(username)

    def authenticate_user(self, username: str, password: str) -> Account | None:
        account = self.auth_repo.get_by_username(username)
        if not account or not account.is_active:
            return None
        if not self.verify_password(password, account.hashed_password):
            return None
        return account

    def create_user(
        self, metadata: AccountCreateRequest, user_role: RoleEnum
    ) -> tuple[Account, str]:
        existing_user = self.get_user_by_username(metadata.username)
        if existing_user:
            raise ValueError(f"Username '{metadata.username}' is already taken.")
        if metadata.role == RoleEnum.student:
            password = settings.STUDENT_DEFAULT_PASSWORD
            first_login = True
        elif metadata.role == RoleEnum.teacher and user_role == RoleEnum.admin:
            password = settings.TEACHER_DEFAULT_PASSWORD
            first_login = True
        elif metadata.role == RoleEnum.teacher and user_role != RoleEnum.admin:
            raise PermissionError("Only admin users can create teacher accounts.")
        else:
            raise ValueError(
                "Only student and teacher accounts can be created via this endpoint."
            )

        hashed_password = self.get_password_hash(password)
        new_account = Account(
            username=metadata.username,
            hashed_password=hashed_password,
            role=metadata.role,
            first_name=metadata.first_name,
            last_name=metadata.last_name,
            first_login=first_login,
        )
        self.auth_repo.create_account(new_account)
        return new_account, password

    def change_password(self, username: str, new_password: str) -> Account:
        user = self.get_user_by_username(username)
        if not user:
            raise ValueError(f"User '{username}' not found.")
        # Changing to the password already in use would clear first_login
        # without replacing the temporary credential.
        if self.verify_password(new_password, user.hashed_password):
            raise ValueError("New password must be different from the current one.")
        return self.auth_repo.change_password(
            user, self.get_password_hash(new_password)
        )

    @staticmethod
    def create_access_token(data: dict[str, Any]) -> str:
        to_encode = data.copy()
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        to_encode.update({"exp": expire})
        token: str = jwt.encode(
            to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
        )
        return token

    @staticmethod
    def create_token_for_user(account: Account) -> str:
        token_data = {
            "sub": account.username,
            "user_id": account.id,
            "role": account.role.value,
        }
        return AuthService.create_access_token(token_data)

    def reset_password(
        self, account_id: int, user_role: RoleEnum
    ) -> tuple[Account, str]:
        if user_role not in (RoleEnum.teacher, RoleEnum.admin):
            raise PermissionError("Only teachers and admins can reset passwords.")
        user = self.auth_repo.get_by_id(account_id)
        if not user:
            raise UserNotFound(f"User with ID '{account_id}' not found.")
        if user.role == RoleEnum.student:
            password = settings.STUDENT_DEFAULT_PASSWORD
        elif user.role == RoleEnum.teacher:
            if user_role != RoleEnum.admin:
                raise PermissionError("You cannot reset other teachers' passwords.")
            password = settings.TEACHER_DEFAULT_PASSWORD
        else:
            raise PermissionError("You cannot reset password for admin account.")
        self.auth_repo.change_password(
            user, self.get_password_hash(password), first_login=True
        )
        return user, password

    def setup_admin_account(self, password: str) -> Account:
        admin_user = self.get_user_by_username("admin")
        if admin_user:
            raise PermissionError("Admin account already exists.")
        hashed_password = self.get_password_hash(password)
        new_admin = Account(
            username="admin",
            hashed_password=hashed_password,
            role=RoleEnum.admin,
            first_name="Admin",
            last_name="User",
        )
        self.auth_repo.create_account(new_admin)
        return new_admin

    def bulk_create_users(
        self, bulk_data: BulkCreateRequest, user_role: RoleEnum
    ) -> BulkCreateResponse:
        if bulk_data.role == RoleEnum.admin:
            raise ValueError("Cannot create admin accounts via bulk endpoint")
        if bulk_data.role == RoleEnum.teacher and user_role != RoleEnum.admin:
            raise PermissionError("Only admins can create teacher accounts.")
        created_accounts = []
        number = self.auth_repo.get_next_prefix_number(bulk_data.prefix)

        for _i in range(bulk_data.count):
            username = f"{bulk_data.prefix}{number:03d}"
            number += 1
            if self.get_user_by_username(username):
                continue

            if bulk_data.role == RoleEnum.student:
                password = settings.STUDENT_DEFAULT_PASSWORD
                first_login = True
            elif bulk_data.role == RoleEnum.teacher:
                password = settings.TEACHER_DEFAULT_PASSWORD
                first_login = True
            else:
                raise ValueError(
                    "Bulk creation is only allowed for students or teachers."
                )
            hashed_password = self.get_password_hash(password)
            new_account = Account(
                username=username,
                hashed_password=hashed_password,
                role=bulk_data.role,
                first_name=bulk_data.role.value,
                last_name="Account",
                first_login=first_login,
            )
            self.auth_repo.create_account(new_account)
            created_accounts.append(
                BulkCredentialItem(
                    username=username, password=password, role=bulk_data.role
                )
            )
        return BulkCreateResponse(
            created=len(created_accounts), accounts=created_accounts
        )

    def get_all_users(self, user_role: RoleEnum | None = None) -> list[AccountRead]:
        if user_role == RoleEnum.teacher:
            accounts = self.auth_repo.get_all_users(role=RoleEnum.student)
        elif user_role == RoleEnum.admin:
            accounts = self.auth_repo.get_all_users()
        else:
            raise PermissionError("Only teachers and admins can list users.")
        return [AccountRead.model_validate(account) for account in accounts]

    def get_user_by_id(self, user_id: int) -> AccountRead:
        if not (account := self.auth_repo.get_by_id(user_id)):
            raise UserNotFound("User not found")
        return AccountRead.model_validate(account)
