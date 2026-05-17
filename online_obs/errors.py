class ApiError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, details: object | None = None):
        super().__init__(message)
        self.message = message
        self.details = details

    def to_dict(self) -> dict:
        payload = {"error": {"code": self.code, "message": self.message}}
        if self.details is not None:
            payload["error"]["details"] = self.details
        return payload


class ValidationError(ApiError):
    status_code = 400
    code = "validation_error"


class UnauthorizedError(ApiError):
    status_code = 401
    code = "unauthorized"


class PayloadTooLargeError(ApiError):
    status_code = 413
    code = "payload_too_large"


class NotFoundError(ApiError):
    status_code = 404
    code = "not_found"


class ConflictError(ApiError):
    status_code = 409
    code = "conflict"


class ServiceUnavailableError(ApiError):
    status_code = 503
    code = "service_unavailable"
