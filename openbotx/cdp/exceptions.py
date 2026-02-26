class CDPError(Exception):
    pass


class CDPBrowserError(CDPError):
    """Raised when the browser's response to a command indicates an error."""

    def __init__(self, obj):
        self.code: int = obj["code"]
        self.message: str = obj["message"]
        self.detail = obj.get("data")

    def __str__(self):
        return f"BrowserError<code={self.code} message={self.message}> {self.detail}"


class CDPConnectionClosed(CDPError):
    """Raised when a public method is called on a closed CDP connection."""

    def __init__(self, reason):
        self.reason = reason

    def __repr__(self):
        return f"{self.__class__.__name__}<{self.reason}>"


class CDPSessionClosed(CDPError):
    pass


class CDPInternalError(CDPError):
    """Raised when there is faulty logic in the CDP integration."""


class CDPEventListenerClosed(CDPError):
    pass
