MASKED_VALUE = "***"

_SENSITIVE_SUFFIXES = ("_key", "_secret", "_token", "_password")
_SENSITIVE_EXACT = frozenset({"token", "password", "secret", "api_key"})


def is_sensitive_key(name: str) -> bool:
    n = name.lower()
    if n in _SENSITIVE_EXACT:
        return True
    return any(n.endswith(s) for s in _SENSITIVE_SUFFIXES)


def mask_dict(d: dict | list) -> dict | list:
    if isinstance(d, list):
        return [mask_dict(v) for v in d]
    if not isinstance(d, dict):
        return d
    masked: dict = {}
    for k, v in d.items():
        if isinstance(v, (dict, list)):
            masked[k] = mask_dict(v)
        elif is_sensitive_key(k):
            masked[k] = MASKED_VALUE if v else ""
        else:
            masked[k] = v
    return masked


def is_masked_or_empty(value: str) -> bool:
    return not value or value == MASKED_VALUE
