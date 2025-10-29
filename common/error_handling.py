"""
Enhanced Error Handling with standardized responses
"""
from typing import Optional, Dict, Any, List
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
import logging
import traceback
import time

logger = logging.getLogger(__name__)

class ErrorDetail(BaseModel):
    """Detailed error information"""
    code: str
    message: str
    field: Optional[str] = None
    context: Optional[Dict[str, Any]] = None

class StandardErrorResponse(BaseModel):
    """Standard error response format"""
    success: bool = False
    error: ErrorDetail
    timestamp: float
    trace_id: Optional[str] = None
    request_id: Optional[str] = None

class ErrorCodes:
    """Standard error codes"""
    # Authentication & Authorization
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    INVALID_TOKEN = "INVALID_TOKEN"
    
    # Validation
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_FIELD = "MISSING_FIELD"
    
    # Business Logic
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
    TRANSFER_FAILED = "TRANSFER_FAILED"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    
    # System Errors
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    DATABASE_ERROR = "DATABASE_ERROR"
    CIRCUIT_BREAKER_OPEN = "CIRCUIT_BREAKER_OPEN"
    
    # External Service Errors
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"

class BusinessLogicError(Exception):
    """Custom exception for business logic errors"""
    def __init__(self, code: str, message: str, field: str = None, context: Dict[str, Any] = None):
        self.code = code
        self.message = message
        self.field = field
        self.context = context or {}
        super().__init__(message)

class ServiceError(Exception):
    """Custom exception for service-level errors"""
    def __init__(self, code: str, message: str, original_error: Exception = None):
        self.code = code
        self.message = message
        self.original_error = original_error
        super().__init__(message)

def create_error_response(
    error_code: str,
    message: str,
    status_code: int = 500,
    field: str = None,
    context: Dict[str, Any] = None,
    trace_id: str = None,
    request_id: str = None
) -> JSONResponse:
    """Create standardized error response"""
    
    error_detail = ErrorDetail(
        code=error_code,
        message=message,
        field=field,
        context=context
    )
    
    error_response = StandardErrorResponse(
        error=error_detail,
        timestamp=time.time(),
        trace_id=trace_id,
        request_id=request_id
    )
    
    return JSONResponse(
        status_code=status_code,
        content=error_response.model_dump()
    )

async def business_logic_exception_handler(request: Request, exc: BusinessLogicError):
    """Handle business logic exceptions"""
    
    # Map business logic errors to HTTP status codes
    status_code_map = {
        ErrorCodes.INSUFFICIENT_FUNDS: 400,
        ErrorCodes.ACCOUNT_NOT_FOUND: 404,
        ErrorCodes.RATE_LIMIT_EXCEEDED: 429,
        ErrorCodes.VALIDATION_ERROR: 400,
    }
    
    status_code = status_code_map.get(exc.code, 400)
    
    # Get trace context
    trace_id = getattr(request.state, 'trace_id', None)
    request_id = getattr(request.state, 'request_id', None)
    
    logger.warning(f"Business logic error: {exc.code} - {exc.message}", extra={
        "error_code": exc.code,
        "trace_id": trace_id,
        "request_id": request_id,
        "field": exc.field,
        "context": exc.context
    })
    
    return create_error_response(
        error_code=exc.code,
        message=exc.message,
        status_code=status_code,
        field=exc.field,
        context=exc.context,
        trace_id=trace_id,
        request_id=request_id
    )

async def service_exception_handler(request: Request, exc: ServiceError):
    """Handle service-level exceptions"""
    
    status_code_map = {
        ErrorCodes.SERVICE_UNAVAILABLE: 503,
        ErrorCodes.DATABASE_ERROR: 503,
        ErrorCodes.CIRCUIT_BREAKER_OPEN: 503,
        ErrorCodes.EXTERNAL_SERVICE_ERROR: 502,
        ErrorCodes.TIMEOUT_ERROR: 504,
    }
    
    status_code = status_code_map.get(exc.code, 500)
    
    trace_id = getattr(request.state, 'trace_id', None)
    request_id = getattr(request.state, 'request_id', None)
    
    logger.error(f"Service error: {exc.code} - {exc.message}", extra={
        "error_code": exc.code,
        "trace_id": trace_id,
        "request_id": request_id,
        "original_error": str(exc.original_error) if exc.original_error else None
    })
    
    return create_error_response(
        error_code=exc.code,
        message=exc.message,
        status_code=status_code,
        trace_id=trace_id,
        request_id=request_id
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation exceptions"""
    
    trace_id = getattr(request.state, 'trace_id', None)
    request_id = getattr(request.state, 'request_id', None)
    
    # Extract first validation error
    first_error = exc.errors()[0]
    field = ".".join(str(loc) for loc in first_error.get("loc", []))
    message = first_error.get("msg", "Validation error")
    
    logger.warning(f"Validation error: {message} on field {field}", extra={
        "trace_id": trace_id,
        "request_id": request_id,
        "validation_errors": exc.errors()
    })
    
    return create_error_response(
        error_code=ErrorCodes.VALIDATION_ERROR,
        message=f"Validation error on field '{field}': {message}",
        status_code=400,
        field=field,
        context={"validation_errors": exc.errors()},
        trace_id=trace_id,
        request_id=request_id
    )

async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle FastAPI HTTP exceptions"""
    
    trace_id = getattr(request.state, 'trace_id', None)
    request_id = getattr(request.state, 'request_id', None)
    
    # Map HTTP status codes to error codes
    status_to_code = {
        401: ErrorCodes.UNAUTHORIZED,
        403: ErrorCodes.FORBIDDEN,
        404: ErrorCodes.ACCOUNT_NOT_FOUND,
        429: ErrorCodes.RATE_LIMIT_EXCEEDED,
        500: ErrorCodes.INTERNAL_SERVER_ERROR,
        503: ErrorCodes.SERVICE_UNAVAILABLE,
    }
    
    error_code = status_to_code.get(exc.status_code, ErrorCodes.INTERNAL_SERVER_ERROR)
    
    logger.warning(f"HTTP exception: {exc.status_code} - {exc.detail}", extra={
        "status_code": exc.status_code,
        "trace_id": trace_id,
        "request_id": request_id
    })
    
    return create_error_response(
        error_code=error_code,
        message=str(exc.detail),
        status_code=exc.status_code,
        trace_id=trace_id,
        request_id=request_id
    )

async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    
    trace_id = getattr(request.state, 'trace_id', None)
    request_id = getattr(request.state, 'request_id', None)
    
    # Log full traceback for debugging
    logger.error(f"Unexpected error: {str(exc)}", extra={
        "trace_id": trace_id,
        "request_id": request_id,
        "traceback": traceback.format_exc()
    })
    
    # Don't expose internal error details in production
    return create_error_response(
        error_code=ErrorCodes.INTERNAL_SERVER_ERROR,
        message="An unexpected error occurred. Please try again later.",
        status_code=500,
        trace_id=trace_id,
        request_id=request_id
    )

def add_error_handlers(app):
    """Add all error handlers to FastAPI app"""
    app.add_exception_handler(BusinessLogicError, business_logic_exception_handler)
    app.add_exception_handler(ServiceError, service_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)