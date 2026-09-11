class ComfyUIMetadataError(Exception):
    """Base exception for metadata and image-container failures."""


class UnsupportedImageContainerError(ComfyUIMetadataError):
    def __init__(self) -> None:
        super().__init__("unsupported image container (expected PNG or WebP)")


class InvalidImageContainerError(ComfyUIMetadataError):
    def __init__(self, container: str) -> None:
        super().__init__(f"invalid {container} container")


class InvalidComfyUIJsonError(ComfyUIMetadataError):
    def __init__(self, key: str, message: str) -> None:
        self.key = key
        super().__init__(f"invalid ComfyUI JSON in {key!r}: {message}")


class MissingWorkflowError(ComfyUIMetadataError):
    def __init__(self) -> None:
        super().__init__("ComfyUI prompt exists but workflow is missing")
