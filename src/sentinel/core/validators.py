"""Pydantic v2 Optimized Validators - Rust-accelerated JSON validation.

Provides optimized validation using Pydantic v2's model_validate_json()
which leverages the Rust-based validation core for 2-5x performance improvement
over standard model_validate() calls on JSON strings.
"""

import json
import logging
from typing import Any, Dict, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def validate_json_model(
    model_class: Type[T], json_str: str, strict: bool = False
) -> Optional[T]:
    """Validate JSON string directly to Pydantic model using Rust-accelerated core.

    Uses model_validate_json() for 2-5x faster validation than:
    - model_validate(json.loads(json_str))
    - model_validate(dict)

    The Rust-based validation core avoids Python JSON deserialization overhead.

    Args:
        model_class: Pydantic model class to validate to.
        json_str: Raw JSON string to validate.
        strict: Enable strict validation mode.

    Returns:
        Validated model instance or None on validation error.

    Example:
        >>> request_data = validate_json_model(ChatRequest, json_payload)
        >>> if request_data:
        ...     await process_request(request_data)
    """
    try:
        # model_validate_json() uses Pydantic's Rust-accelerated parser
        # This is significantly faster than model_validate(json.loads(...))
        return model_class.model_validate_json(json_str, strict=strict)
    except ValidationError as e:
        logger.warning(
            f"JSON validation failed for {model_class.__name__}: {e.error_count()} errors"
        )
        # Log first error for debugging
        if e.errors():
            logger.debug(f"First validation error: {e.errors()[0]}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON provided: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during JSON validation: {e}")
        return None


def validate_dict_model(model_class: Type[T], data: Dict[str, Any]) -> Optional[T]:
    """Validate dictionary to Pydantic model.

    Use model_validate_json(json.dumps(data)) for JSON strings instead.

    Args:
        model_class: Pydantic model class to validate to.
        data: Dictionary to validate.

    Returns:
        Validated model instance or None on validation error.
    """
    try:
        return model_class.model_validate(data)
    except ValidationError as e:
        logger.warning(
            f"Dict validation failed for {model_class.__name__}: {e.error_count()} errors"
        )
        return None
    except Exception as e:
        logger.error(f"Unexpected error during dict validation: {e}")
        return None


def get_schema_info(model_class: Type[BaseModel]) -> Dict[str, Any]:
    """Get compiled schema info for a Pydantic model.

    Returns schema information including whether it's using
    Rust-accelerated validation.

    Args:
        model_class: Pydantic model class.

    Returns:
        Dictionary with schema information.
    """
    return {
        "model": model_class.__name__,
        "fields": list(model_class.model_fields.keys()),
        "schema_version": "v2_compiled",  # Indicates Rust-accelerated
    }
