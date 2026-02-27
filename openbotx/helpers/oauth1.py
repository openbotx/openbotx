"""OAuth 1.0a signature generation (RFC 5849)."""

import base64
import hashlib
import hmac
import time
import uuid
from urllib.parse import parse_qsl, quote, urlparse, urlunparse


def _pct_encode(value: str) -> str:
    return quote(str(value), safe="")


def build_oauth1_header(
    method: str,
    url: str,
    consumer_key: str,
    consumer_secret: str,
    access_token: str,
    access_token_secret: str,
    body_params: list[tuple[str, str]] | None = None,
) -> str:
    """Build an OAuth 1.0a Authorization header using HMAC-SHA1.

    Per RFC 5849:
    - Query parameters from the URL are included in the signature base string
    - The base URL used for signing has the query string stripped
    - Body parameters (for application/x-www-form-urlencoded) are included
    - All parameters are percent-encoded and sorted for the signature

    Returns the full header value, e.g. ``OAuth oauth_consumer_key="...", ...``
    """
    oauth = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": uuid.uuid4().hex,
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(int(time.time())),
        "oauth_token": access_token,
        "oauth_version": "1.0",
    }

    # Parse URL to separate base URL from query params (RFC 5849 Section 3.4.1.2)
    parsed = urlparse(url)
    base_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

    # Collect all parameters: oauth + query string + body params
    all_params: list[tuple[str, str]] = list(oauth.items())
    all_params.extend(parse_qsl(parsed.query, keep_blank_values=True))
    if body_params:
        all_params.extend(body_params)

    # RFC 5849 Section 3.4.1.3.2: sort by encoded key, then encoded value
    sorted_params = "&".join(
        f"{_pct_encode(k)}={_pct_encode(v)}"
        for k, v in sorted(all_params, key=lambda p: (_pct_encode(p[0]), _pct_encode(p[1])))
    )
    base_string = f"{method.upper()}&{_pct_encode(base_url)}&{_pct_encode(sorted_params)}"
    signing_key = f"{_pct_encode(consumer_secret)}&{_pct_encode(access_token_secret)}"

    signature = base64.b64encode(
        hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
    ).decode()
    oauth["oauth_signature"] = signature

    parts = [f'{_pct_encode(k)}="{_pct_encode(v)}"' for k, v in sorted(oauth.items())]
    return "OAuth " + ", ".join(parts)
