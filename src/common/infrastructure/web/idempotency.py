import functools
from flask import request, jsonify, current_app

# In-memory store for idempotency. Replace with Redis for production multi-instance deployments.
_idempotency_store = {}

def idempotent(view_func):
    @functools.wraps(view_func)
    def wrapped(*args, **kwargs):
        if request.method != 'POST':
            return view_func(*args, **kwargs)
            
        idempotency_key = request.headers.get('Idempotency-Key')
        
        if not idempotency_key:
            return view_func(*args, **kwargs)
            
        request_signature = f"{request.path}:{idempotency_key}"
        
        if request_signature in _idempotency_store:
            current_app.logger.info(f"Idempotency Key hit: {idempotency_key}")
            return _idempotency_store[request_signature]
            
        response = view_func(*args, **kwargs)
        
        # Only cache successful responses (2xx)
        if 200 <= response.status_code < 300:
            _idempotency_store[request_signature] = response
            
        return response
    return wrapped