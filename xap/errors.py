"""XAP error hierarchy."""


class XAPError(Exception):
    """Base error for all XAP operations."""


class XAPValidationError(XAPError):
    """Schema or type validation failed."""


class XAPCryptoError(XAPError):
    """Cryptographic operation failed."""


class XAPStateError(XAPError):
    """Invalid state machine transition."""


class XAPAdapterError(XAPError):
    """Settlement adapter operation failed."""


class XAPBuilderError(XAPError):
    """Builder is missing required fields or produced invalid output."""
