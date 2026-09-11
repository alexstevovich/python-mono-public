class A1111MetadataError(Exception):
    """Base error for Automatic1111/Forge metadata operations."""


class MetadataVerificationError(A1111MetadataError):
    """Raised when newly written metadata cannot be read back exactly."""
