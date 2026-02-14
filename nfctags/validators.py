import re
import uuid

from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError


def is_valid_uuid(uuid_str):
    try:
        # Attempt to create a UUID object. You can specify the version if needed.
        uuid_obj = uuid.UUID(uuid_str, version=4)
    except ValueError:
        return False
    # Optional: Ensure that the canonical string representation matches the input.
    return str(uuid_obj) == uuid_str


def parse_ascii_mirror(value):
    """
    Parse the ASCII Mirror-Based UID and counter format.

    Args:
        value (str): The ASCII mirror value to be parsed.

    Returns:
        tuple: (uid, counter) where counter may be None.

    Raises:
        ValidationError: If the input value is empty or if the format is invalid.
    """
    if not value:
        raise ValidationError(_("Input value cannot be empty."))

    if 'x' in value:
        parts = value.split('x', 1)
        if len(parts) != 2:
            raise ValidationError(_("Invalid format. Expected 'UIDxCounter'."))
        uid, counter = parts
        uid = validate_ascii_component(uid, 'uid')
        counter = validate_ascii_component(counter, 'counter')
        return uid, counter

    return validate_ascii_component(value, 'uid'), None


def validate_ascii_component(value, component_type):
    """
    Validates a component (either UID or counter) of an ASCII mirror.

    Args:
        value (str): The value to be validated.
        component_type (str): The type of component to validate ('uid' or 'counter').

    Returns:
        str: The validated component value.

    Raises:
        ValidationError: If an invalid component type is provided or if the validation fails.
    """
    if component_type == 'uid':
        return validate_ascii_mirror_uid(value)
    elif component_type == 'counter':
        return validate_ascii_mirror_counter(value)
    raise ValidationError(_("Invalid component type for validation."))


def validate_ascii_mirror_uid(value):
    """
    Validates the ASCII Mirror-Based NTAG uid format.
    The uid should be a 7-byte (14 characters) hex value in ASCII representation.
    """
    pattern = re.compile(r'^[0-9A-Fa-f]{14}$')
    if not pattern.match(value):
        return None
    return value


def validate_ascii_mirror_counter(value):
    """
    Validate the ASCII Mirror-Based counter format.
    The counter should be a 3-byte(6 characters) hex value in ASCII representation.
    """
    pattern = re.compile(r'^[0-9A-Fa-f]{6}$')
    if not pattern.match(value):
        return None

    if isinstance(value, int):
        return value

    elif isinstance(value, bytes):
        try:
            return int(value.decode('utf-8'))
        except ValueError:
            return None

    elif isinstance(value, str):
        try:
            return int(value, 16)  # Convert from hex if necessary
        except ValueError:
            return None

    else:
        return None  # raise ValidationError("Counter must be an int, bytes, or str")
