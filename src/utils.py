import logging
from functools import wraps
from fastapi import (
    Request, 
    HTTPException,
    Header,
)

from twilio.request_validator import RequestValidator


# settings
from .settings import (
    TWILIO_AUTH_TOKEN,
    LOGGER_NAME,
)

logger = logging.getLogger(LOGGER_NAME)

def validate_twilio_request(f):
    """Validates that incoming requests genuinely originated from Twilio"""
    @wraps(f)
    async def decorated_function(request: Request, x_twilio_signature: str = Header(None), *args, **kwargs):
        
        validator = RequestValidator(TWILIO_AUTH_TOKEN)

        # Validate the request using its URL, POST data,
        # and X-TWILIO-SIGNATURE header
        form_data = await request.form()
        request_valid = validator.validate(
            str(request.url),
            form_data,
            x_twilio_signature or "",
        )

        # Continue processing the request if it's valid, return a 403 error if
        # it's not
        if request_valid:
            return await f(*args, **kwargs)
        else:
            logger.error("Twilio Request Validation Failed")
            return HTTPException(
                status_code=403,
                detail="Twilio Request Validation Failed"
            )
        
    return decorated_function
