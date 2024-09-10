from fastapi import HTTPException, status


class UserError(HTTPException):
    STATUS_CODE: int
    ERROR_MESSAGE: str

    def __init__(self):
        super().__init__(
            status_code=self.STATUS_CODE,
            detail=self.ERROR_MESSAGE,
        )


class InvalidFileTypeError(UserError):
    ERROR_MESSAGE = "Invalid file type. Only valid .ipa or .apk files are allowed."
    STATUS_CODE = status.HTTP_400_BAD_REQUEST


class UnauthorizedError(UserError):
    ERROR_MESSAGE = "Invalid X-Auth-Token"
    STATUS_CODE = status.HTTP_403_FORBIDDEN


class NotFoundError(UserError):
    ERROR_MESSAGE = "Not found"
    STATUS_CODE = status.HTTP_404_NOT_FOUND


class InternalServerError(UserError):
    ERROR_MESSAGE = "Internal server error"
    STATUS_CODE = status.HTTP_500_INTERNAL_SERVER_ERROR


default_exception_types: list[type[UserError]] = [
    InternalServerError,
    NotFoundError,
    UnauthorizedError,
]

status_codes_to_default_exception_types = {
    exception_type.STATUS_CODE: exception_type  # fmt: skip
    for exception_type in default_exception_types
}
