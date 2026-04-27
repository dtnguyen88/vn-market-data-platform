"""Validate Pub/Sub message body against a Pydantic model. Reject on failure."""

from pydantic import BaseModel, ValidationError


def validate[T: BaseModel](body: bytes, model_cls: type[T]) -> T | None:
    """Return a validated model instance or None if body fails validation."""
    try:
        return model_cls.model_validate_json(body)
    except ValidationError:
        return None
