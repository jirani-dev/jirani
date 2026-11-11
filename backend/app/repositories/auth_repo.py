from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, RoleEnum


class AuthRepo:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def get_by_username(self, username: str) -> Account | None:
        return self.db_session.scalars(
            select(Account).where(Account.username == username)
        ).first()

    def get_by_id(self, account_id: int) -> Account | None:
        return self.db_session.scalars(
            select(Account).where(Account.id == account_id)
        ).first()

    def create_account(self, account: Account) -> Account:
        self.db_session.add(account)
        try:
            self.db_session.commit()
        except IntegrityError:
            self.db_session.rollback()
            raise
        self.db_session.refresh(account)
        return account

    def get_all_users(self, role: RoleEnum | None = None) -> list[Account]:
        # Explicit order: without ORDER BY the row order is unspecified and
        # changes after an UPDATE (a password reset, for instance).
        stmt = select(Account).order_by(Account.id)
        if role is not None:
            stmt = stmt.where(Account.role == role)
        return list(self.db_session.scalars(stmt))

    def change_password(
        self, account: Account, new_hashed_password: str, *, first_login: bool = False
    ) -> Account:
        account.hashed_password = new_hashed_password
        account.first_login = first_login
        self.db_session.commit()
        self.db_session.refresh(account)
        return account

    def get_next_prefix_number(self, prefix: str) -> int:
        # autoescape: the prefix is user input, and "%" / "_" in it must match
        # themselves rather than act as LIKE wildcards.
        usernames = self.db_session.scalars(
            select(Account.username).where(
                Account.username.startswith(prefix, autoescape=True)
            )
        )
        # ASCII digits only: str.isdigit() alone also accepts characters such
        # as "²" that int() cannot parse.
        numbers = [
            int(suffix)
            for username in usernames
            if (suffix := username.removeprefix(prefix)).isascii() and suffix.isdigit()
        ]
        return max(numbers) + 1 if numbers else 1
