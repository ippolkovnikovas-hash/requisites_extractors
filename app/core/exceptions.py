class AppException(Exception):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class UnsupportedFileTypeError(AppException):
    pass


class TextExtractionError(AppException):
    pass


class LLMError(AppException):
    pass


class LLMParseError(AppException):
    pass


class ValidationError(AppException):
    pass


class ExportError(AppException):
    pass
