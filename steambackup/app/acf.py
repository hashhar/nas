__all__ = ("load", "loads")

from typing import Any, Dict, List, NamedTuple, TextIO


SECTION_START = "{"
SECTION_END = "}"


class AppManifest(NamedTuple):
    name: str
    install_dir: str
    size_on_disk: int
    build_id: int
    download_size: int


def loads_as_obj(data: str) -> AppManifest:
    """
    Loads ACF content into an AppManifest object.
    :param data: An UTF-8 encoded content of an ACF file.
    :return: An AppManifest object with ACF data.
    """
    parsed = loads(data)
    try:
        return AppManifest(
            name=parsed["AppState"]["name"],
            install_dir=parsed["AppState"]["installdir"],
            build_id=parsed["AppState"].get("buildid"),
            size_on_disk=parsed["AppState"].get("SizeOnDisk"),
            download_size=parsed["AppState"].get("BytesDownloaded"),
        )
    except Exception:
        raise Exception(
            f"Failed while converting to AppManifest, parsed object was: {parsed}"
        )


def loads(data: str) -> Dict[str, Any]:
    """
    Loads ACF content into a Python object.
    :param data: An UTF-8 encoded content of an ACF file.
    :return: A dictionary with ACF data.
    """
    parsed: Dict[str, Any] = {}
    current_section = parsed
    sections: List[str] = []

    lines = (line.strip() for line in data.splitlines())

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


def load_as_obj(file: TextIO) -> AppManifest:
    """
    Loads the contents of an ACF file into an AppManifest object.
    :param file: A file object.
    :return: An AppManifest object with ACF data.
    """
    return loads_as_obj(file.read())


def load(file: TextIO):
    """
    Loads the contents of an ACF file into a Python object.
    :param file: A file object.
    :return: An Ordered Dictionary with ACF data.
    """
    return loads(file.read())


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
