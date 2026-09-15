class AuthError(Exception):
    pass


class UserNotFound(AuthError):
    pass
