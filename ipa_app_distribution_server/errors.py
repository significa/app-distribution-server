from fastapi import HTTPException, status


class APIUserError(HTTPException):
    STATUS_CODE: int
    ERROR_MESSAGE: str

    def __init__(self):
        super().__init__(
            status_code=self.STATUS_CODE,
            detail=self.ERROR_MESSAGE,
        )


class InvalidFileTypeError(APIUserError):
    ERROR_MESSAGE = "Invalid file type. Only valid .ipa files are allowed."
    STATUS_CODE = status.HTTP_400_BAD_REQUEST


class UnauthorizedError(APIUserError):
    ERROR_MESSAGE = "Invalid X-Auth-Token"
    STATUS_CODE = status.HTTP_403_FORBIDDEN


class NotFoundError(APIUserError):
    ERROR_MESSAGE = "Not found"
    STATUS_CODE = status.HTTP_404_NOT_FOUND
