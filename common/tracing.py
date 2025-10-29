"""
Distributed Tracing implementation for microservices
Simple correlation ID-based tracing across services
"""
import uuid
import time
import json
from typing import Dict, Optional, List
from contextvars import ContextVar
from fastapi import Request
import logging

logger = logging.getLogger(__name__)

# Context variables for tracing
trace_id_var: ContextVar[Optional[str]] = ContextVar('trace_id', default=None)
span_id_var: ContextVar[Optional[str]] = ContextVar('span_id', default=None)

class TraceSpan:
    """Simple span implementation for tracing"""
    
    def __init__(self, name: str, trace_id: str = None, parent_span_id: str = None):
        self.span_id = str(uuid.uuid4())[:8]
        self.trace_id = trace_id or str(uuid.uuid4())[:16]
        self.parent_span_id = parent_span_id
        self.name = name
        self.start_time = time.time()
        self.end_time = None
        self.tags = {}
        self.logs = []
        self.status = "ok"
        
        # Set context variables
        trace_id_var.set(self.trace_id)
        span_id_var.set(self.span_id)
    
    def add_tag(self, key: str, value: str):
        """Add tag to span"""
        self.tags[key] = value
        return self
    
    def add_log(self, message: str, level: str = "info"):
        """Add log entry to span"""
        self.logs.append({
            "timestamp": time.time(),
            "level": level,
            "message": message
        })
        return self
    
    def set_error(self, error: Exception):
        """Mark span as error"""
        self.status = "error"
        self.add_tag("error", True)
        self.add_tag("error.type", type(error).__name__)
        self.add_tag("error.message", str(error))
        return self
    
    def finish(self):
        """Finish the span"""
        self.end_time = time.time()
        duration_ms = (self.end_time - self.start_time) * 1000
        
        # Log structured trace data
        trace_data = {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation": self.name,
            "duration_ms": round(duration_ms, 2),
            "status": self.status,
            "tags": self.tags,
            "logs": self.logs,
            "timestamp": self.start_time
        }
        
        logger.info(f"TRACE: {json.dumps(trace_data)}")
        return self
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.set_error(exc_val)
        self.finish()

class Tracer:
    """Simple tracer for creating spans"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
    
    def start_span(self, name: str, trace_id: str = None, parent_span_id: str = None) -> TraceSpan:
        """Start a new span"""
        span = TraceSpan(name, trace_id, parent_span_id)
        span.add_tag("service.name", self.service_name)
        return span
    
    def start_span_from_request(self, request: Request, operation_name: str) -> TraceSpan:
        """Start span from HTTP request headers"""
        trace_id = request.headers.get("X-Trace-ID")
        parent_span_id = request.headers.get("X-Span-ID")
        
        span = self.start_span(operation_name, trace_id, parent_span_id)
        span.add_tag("http.method", request.method)
        span.add_tag("http.url", str(request.url))
        
        # Add user info if available
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            span.add_tag("user.authenticated", True)
        
        return span

# Global tracer instances
shard_manager_tracer = Tracer("shard-manager")
auth_tracer = Tracer("auth-service")
fraud_tracer = Tracer("fraud-service")
analytics_tracer = Tracer("analytics-service")
notification_tracer = Tracer("notification-service")

def get_current_trace_id() -> Optional[str]:
    """Get current trace ID from context"""
    return trace_id_var.get()

def get_current_span_id() -> Optional[str]:
    """Get current span ID from context"""
    return span_id_var.get()

def get_trace_headers() -> Dict[str, str]:
    """Get headers for propagating trace context"""
    headers = {}
    trace_id = get_current_trace_id()
    span_id = get_current_span_id()
    
    if trace_id:
        headers["X-Trace-ID"] = trace_id
    if span_id:
        headers["X-Span-ID"] = span_id
    
    return headers

# Middleware for automatic tracing
async def tracing_middleware(request: Request, call_next, tracer: Tracer):
    """FastAPI middleware for automatic request tracing"""
    operation_name = f"{request.method} {request.url.path}"
    
    with tracer.start_span_from_request(request, operation_name) as span:
        try:
            response = await call_next(request)
            span.add_tag("http.status_code", response.status_code)
            
            if response.status_code >= 400:
                span.add_tag("error", True)
                span.status = "error"
            
            # Add trace headers to response
            response.headers["X-Trace-ID"] = span.trace_id
            response.headers["X-Span-ID"] = span.span_id
            
            return response
            
        except Exception as e:
            span.set_error(e)
            raise