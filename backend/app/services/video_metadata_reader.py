import shutil
import subprocess
from pathlib import Path
from uuid import uuid4


class VideoMetadataReader:
    def poster(self, source: Path, dest_dir: Path) -> str | None:
        if shutil.which("ffmpeg") is None:
            return None
        name = f"{uuid4()}.jpg"
        dest = dest_dir / name
        try:
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-ss",
                    "1",
                    "-i",
                    str(source),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=480:-2",
                    str(dest),
                ],
                capture_output=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0 or not dest.is_file():
            return None
        return name
