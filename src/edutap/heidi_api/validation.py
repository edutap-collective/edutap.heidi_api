"""Runtime guards for identifiers whose format is fixed by contract.

``pass_id``/``template_id`` are ``format: uuid`` in the upstream OpenAPI
spec. ``person_id`` has no upstream format, but the eduTAP domain always
addresses persons by a SAML scoped identifier.
"""

import re
from uuid import UUID


def to_uuid_segment(value: UUID | str, param_name: str) -> str:
    """Validate an identifier and render it as a canonical UUID path segment.

    Kept as a runtime guard even though callers are typed ``UUID``: Python
    does not enforce annotations at runtime, so a caller that bypasses the
    type checker (or does not run one) is still protected from splicing a
    path-traversal or query-injection value into a URL.

    :param param_name: name of the caller-facing argument ``value`` came
        from, used to name it in the error message.
    :raises ValueError: if ``value`` is not a valid UUID.
    """
    try:
        return str(UUID(str(value)))
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError(f"{param_name} is not a valid UUID: {value!r}") from exc


_SCOPED_ID_RE = re.compile(r"^[A-Za-z0-9=._-]{1,256}@[A-Za-z0-9.-]{1,127}$")


def validate_person_id(value: str) -> str:
    """Validate a person identifier as a SAML scoped identifier.

    eduTAP addresses persons by one of four SAML identifier types
    (eduPersonPrincipalName, eduPersonUniqueId, subject-id, pairwise-id);
    all share the scoped form ``<local>@<scope>``. The character sets and
    length bounds here are the conservative union of those four profiles.

    HEIDI's own OpenAPI declares ``person_id`` only as ``string``; this
    stricter check is an eduTAP-domain constraint, not an upstream one.
    """
    if _SCOPED_ID_RE.fullmatch(value):
        return value
    raise ValueError(
        f"person_id is not a valid scoped identifier "
        f"(expected <local>@<scope>): {value!r}"
    )
