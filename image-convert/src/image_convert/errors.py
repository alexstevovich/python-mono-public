class ImageConvertError(Exception):
    """Base exception for image conversion failures."""


class UnsupportedInputError(ImageConvertError):
    def __init__(self) -> None:
        super().__init__("unsupported input format")


class UnsupportedOutputError(ImageConvertError):
    def __init__(self) -> None:
        super().__init__(
            "unsupported output format (use .png, .jpg/.jpeg, .webp, or .gif)"
        )


class AnimationToStillError(ImageConvertError):
    def __init__(self) -> None:
        super().__init__("animated input cannot be written to a still-only format")


class InvalidTransformError(ImageConvertError):
    def __init__(self, message: str) -> None:
        super().__init__(f"invalid transform: {message}")


class InvalidEncodeOptionError(ImageConvertError):
    pass


class OutputVerificationError(ImageConvertError):
    pass
