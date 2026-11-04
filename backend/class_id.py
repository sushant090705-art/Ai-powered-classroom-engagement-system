"""Class / room identifiers (point 12: multi-camera, multi-class).

Every live camera belongs to one class id. The old single-camera API keeps
working because a request without a class id uses DEFAULT_CLASS_ID.
"""

import re

DEFAULT_CLASS_ID = "default"

_CLASS_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


def normalize_class_id(value):
    """Return a safe class id, or raise ValueError.

    None / "" mean the default class. Only letters, digits, "_" and "-"
    are allowed, because the id is also used in folder names.
    """

    if value is None or str(value).strip() == "":
        return DEFAULT_CLASS_ID

    value = str(value).strip()

    if not _CLASS_ID_PATTERN.match(value):
        raise ValueError(
            "class_id may only contain letters, digits, '-' and '_' "
            "(max 40 characters)."
        )

    return value
