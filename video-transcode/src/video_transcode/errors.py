class VideoTranscodeError(Exception):
    """Base error for expected transcoding failures."""


class ProbeError(VideoTranscodeError):
    pass


class ValidationError(VideoTranscodeError):
    pass


class BinaryNotFoundError(VideoTranscodeError):
    pass


class TranscodeExecutionError(VideoTranscodeError):
    def __init__(self, message: str, command: tuple[str, ...], returncode: int):
        super().__init__(message)
        self.command = command
        self.returncode = returncode
