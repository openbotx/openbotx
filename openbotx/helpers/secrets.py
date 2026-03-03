SENSITIVE_SUFFIXES = ("_key", "_secret", "_token", "_password")
SENSITIVE_EXACT = frozenset({"key", "token", "password", "secret", "api_key", "value"})


def is_sensitive_key(name: str) -> bool:
    n = name.lower()
    if n in SENSITIVE_EXACT:
        return True
    return any(n.endswith(s) for s in SENSITIVE_SUFFIXES)


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
            masked[k] = ""
        else:
            masked[k] = v
    return masked


def is_empty_or_blank(value: str) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and not value.strip()
