from pathlib import Path


def write_new_file(target: Path, data: bytes) -> None:
    """Create ``target`` holding ``data``.

    The file must not exist yet: a name clash fails instead of overwriting a
    file that something else refers to. A write that fails part-way, on a full
    disk for instance, removes what it wrote, so a failed upload never leaves
    a partial file behind.
    """
    file = target.open("xb")
    try:
        with file:
            file.write(data)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
