__all__ = ("load", "load_as_app_manifest")

from pathlib import Path
from typing import Any, Dict, List, NamedTuple, TextIO

SECTION_START = "{"
SECTION_END = "}"

APP_STATE_KEY = "AppState"
APP_ID_KEY = "appid"
NAME_KEY = "name"
INSTALL_DIR_KEY = "installdir"
SIZE_ON_DISK_KEY = "SizeOnDisk"
BUILD_ID_KEY = "buildid"
DOWNLOAD_SIZE_KEY = "BytesDownloaded"


class AppManifest(NamedTuple):
    manifest_path: Path
    app_id: int
    name: str
    install_dir: str
    size_on_disk: int
    build_id: int
    download_size: int


def load_as_app_manifest(file: TextIO) -> AppManifest:
    """
    Loads the contents of an ACF file into an AppManifest object.
    :param file: A file object.
    :return: An AppManifest object with ACF data.
    """
    parsed = load(file)
    try:
        if APP_STATE_KEY in parsed:
            app_state = parsed[APP_STATE_KEY]
            return AppManifest(
                manifest_path=Path(file.name).resolve(True),
                app_id=app_state.get(APP_ID_KEY),
                name=app_state.get(NAME_KEY),
                install_dir=app_state.get(INSTALL_DIR_KEY),
                size_on_disk=app_state.get(SIZE_ON_DISK_KEY),
                build_id=app_state.get(BUILD_ID_KEY),
                download_size=app_state.get(DOWNLOAD_SIZE_KEY),
            )
        else:
            raise Exception(f"Expected {APP_STATE_KEY} to be present")
    except Exception:
        raise Exception(
            f"Failed while converting to AppManifest, parsed object was: {parsed}"
        )


def load(file: TextIO) -> Dict[str, Any]:
    """
    Loads the contents of an ACF file into a Python object.
    :param file: A file object.
    :return: An Ordered Dictionary with ACF data.
    """
    parsed: Dict[str, Any] = {}
    current_section = parsed
    sections: List[str] = []

    lines = (line.strip() for line in file.read().splitlines())

    for line in lines:
        try:
            key, value = line.split(None, 1)
            key = key.replace('"', "").lstrip()
            value = value.replace('"', "").rstrip()
        except ValueError:
            if line == SECTION_START:
                # Initialize the last added section.
                current_section = _prepare_subsection(parsed, sections)
            elif line == SECTION_END:
                # Remove the last section from the queue.
                sections.pop()
            else:
                # Add a new section to the queue.
                sections.append(line.replace('"', ""))
            continue

        current_section[key] = value

    return parsed


def _prepare_subsection(data: Dict[str, Any], sections: List[str]) -> Dict[str, Any]:
    """
    Creates a subsection ready to be filled.
    :param data: Semi-parsed dictionary.
    :param sections: A list of sections.
    :return: A newly created subsection.
    """
    current: Dict[str, Any] = data
    for section in sections[:-1]:
        current = current[section]

    current[sections[-1]] = {}
    return current[sections[-1]]
