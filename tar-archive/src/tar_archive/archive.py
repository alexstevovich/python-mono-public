import os
import stat
import tarfile
from contextlib import ExitStack, contextmanager
from pathlib import Path, PurePosixPath

from .console import print_message
from .encryption import encrypted_writer

TARGET_BUFFER_SIZE = 8 * 1024 * 1024
TAR_BUFFER_SIZE = 1024 * 1024
ZSTD_LEVEL = 3


def create_tar(
    source: str | Path,
    archive_path: str | Path,
    *,
    compression: bool = False,
    encryption: str | None = None,
) -> Path:
    """Stream one directory into a new TAR, optionally compressed with Zstd."""
    source = Path(source).absolute()
    final_path = Path(archive_path).absolute()

    if not source.is_dir() or _is_link_like(source):
        raise ValueError(f"Source must be a regular directory: {source}")

    partial_path = Path(f"{final_path}.part")

    if not final_path.parent.is_dir():
        raise NotADirectoryError(
            f"Archive output directory does not exist: {final_path.parent}"
        )
    if final_path.exists():
        raise FileExistsError(f"Archive already exists: {final_path}")

    print()
    print_message("ARCHIVE", str(source), "cyan")
    print_message("OUTPUT", str(final_path), "cyan")
    print_message(
        "COMPRESSION", "Zstandard level 3" if compression else "None", "yellow"
    )
    print_message("ENCRYPTION", "AES-256-GCM" if encryption else "None", "yellow")

    partial_created = False
    try:
        with partial_path.open("xb", buffering=TARGET_BUFFER_SIZE) as output:
            partial_created = True
            with _open_archive(output, compression, encryption) as archive:
                _add_directory_tree(archive, source)

            output.flush()
            os.fsync(output.fileno())

        partial_path.rename(final_path)
    except BaseException:
        if partial_created:
            partial_path.unlink(missing_ok=True)
        raise

    size = final_path.stat().st_size
    print_message("COMPLETE", f"{final_path} ({size:,} bytes)", "green")
    return final_path


@contextmanager
def _open_archive(output, compression: bool, encryption: str | None):
    tar_options = {
        "format": tarfile.PAX_FORMAT,
        "dereference": False,
        "bufsize": TAR_BUFFER_SIZE,
    }

    with ExitStack() as stack:
        stream = output
        if encryption:
            stream = stack.enter_context(encrypted_writer(stream, encryption))

        if compression:
            try:
                from compression import zstd
            except ImportError as exc:
                raise RuntimeError(
                    "Zstandard compression requires Python 3.14 with compression.zstd"
                ) from exc
            stream = stack.enter_context(
                zstd.ZstdFile(stream, mode="wb", level=ZSTD_LEVEL)
            )

        archive = stack.enter_context(
            tarfile.open(fileobj=stream, mode="w|", **tar_options)
        )
        yield archive


def _add_directory_tree(archive: tarfile.TarFile, source: Path) -> None:
    """Add a tree explicitly so no link-like directory is ever followed."""
    root_name = PurePosixPath(source.name)
    archive.add(source, arcname=root_name.as_posix(), recursive=False)

    pending = [(source, root_name)]
    while pending:
        directory, archive_directory = pending.pop()
        with os.scandir(directory) as entries:
            children = sorted(entries, key=lambda entry: entry.name.casefold())

        directories = []
        for entry in children:
            path = Path(entry.path)
            archive_path = archive_directory / entry.name

            if _entry_is_link_like(entry):
                _add_link(archive, path, archive_path, _link_kind(entry))
            elif entry.is_dir(follow_symlinks=False):
                archive.add(path, arcname=archive_path.as_posix(), recursive=False)
                directories.append((path, archive_path))
            elif entry.is_file(follow_symlinks=False):
                archive.add(path, arcname=archive_path.as_posix(), recursive=False)
            else:
                print_message(
                    "SKIPPED", f"Unsupported filesystem object: {path}", "magenta"
                )

        pending.extend(reversed(directories))


def _add_link(
    archive: tarfile.TarFile,
    path: Path,
    archive_path: PurePosixPath,
    link_kind: str,
) -> None:
    try:
        link_target = os.readlink(path)
    except OSError as exc:
        raise RuntimeError(f"Cannot preserve reparse-point link: {path}") from exc

    item_stat = path.lstat()
    info = tarfile.TarInfo(archive_path.as_posix())
    info.type = tarfile.SYMTYPE
    info.linkname = link_target
    info.mode = stat.S_IMODE(item_stat.st_mode)
    info.mtime = item_stat.st_mtime
    info.size = 0
    info.pax_headers["backup.windows_link_type"] = link_kind
    reparse_tag = getattr(item_stat, "st_reparse_tag", None)
    if reparse_tag is not None:
        info.pax_headers["backup.windows_reparse_tag"] = str(reparse_tag)
    archive.addfile(info)


def _is_link_like(path: Path) -> bool:
    if path.is_symlink():
        return True
    if hasattr(path, "is_junction") and path.is_junction():
        return True
    item_stat = path.lstat()
    attributes = getattr(item_stat, "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _entry_is_link_like(entry: os.DirEntry) -> bool:
    if entry.is_symlink():
        return True
    if hasattr(entry, "is_junction") and entry.is_junction():
        return True
    item_stat = entry.stat(follow_symlinks=False)
    attributes = getattr(item_stat, "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _link_kind(entry: os.DirEntry) -> str:
    if entry.is_symlink():
        return "symlink"
    if hasattr(entry, "is_junction") and entry.is_junction():
        return "junction"
    return "other_reparse_point"
