#!/usr/bin/env python3

import argparse
import hashlib
import logging
import os
from pathlib import Path
from typing import Any, NamedTuple

import exceptions
import acf
from acf import AppManifest

STEAMAPPS_DIRECTORY = "steamapps"
COMMON_DIRECTORY = "common"
MUSIC_DIRECTORY = "music"

MODE_SYNC = "sync"
MODE_OVERWRITE = "overwrite"

INSTALL_DIR_OVERRIDES = {
    20930: "the witcher 2",
}


class Arguments(NamedTuple):
    steam_library: Path
    destination: Path
    mode: str


def parse_arguments() -> Arguments:
    def require_directory_exists(arg: str) -> Path:
        path = Path(arg)
        if path.exists() and path.is_dir():
            return path.resolve(True)

        raise exceptions.InvalidArgumentException(
            f"'{arg}' does not exist or is not a directory"
        )

    def require_steam_library_exists(arg: str) -> Path:
        steamapps_path = Path(arg, STEAMAPPS_DIRECTORY)
        if steamapps_path.exists() and steamapps_path.is_dir():
            return Path(arg).resolve(True)

        raise exceptions.InvalidArgumentException(
            f"'{arg}' does not exist or doesn't contain a"
            f" {STEAMAPPS_DIRECTORY} subdirectory"
        )

    parser = argparse.ArgumentParser(description="Backup Steam library")
    parser.add_argument(
        "--steam-library",
        required=True,
        metavar="PATH",
        help=(
            "Path to the Steam library i.e. the directory containing the steamapps"
            " subdirectory."
        ),
    )
    parser.add_argument(
        "--destination",
        required=True,
        metavar="PATH",
        help=(
            "Path to backup destination where archives will be created (or already"
            " exist)."
        ),
    )
    parser.add_argument(
        "--mode",
        required=True,
        metavar="MODE",
        choices=[MODE_SYNC, MODE_OVERWRITE],
        help=(
            "'sync' will update archives if they exist otherwise will create new ones."
            " 'overwrite' will create new archives if required and overwrite any"
            " existing ones."
        ),
    )
    parsed: dict[str, Any] = vars(parser.parse_args())
    logging.debug("Parsed arguments: %s", parsed)
    parsed["steam_library"] = require_steam_library_exists(parsed["steam_library"])
    parsed["destination"] = require_directory_exists(parsed["destination"])

    return Arguments(**parsed)


def steam_games_directory(steam_library: Path) -> Path:
    return Path(steam_library, STEAMAPPS_DIRECTORY, COMMON_DIRECTORY)


def steam_music_directory(steam_library: Path) -> Path:
    return Path(steam_library, STEAMAPPS_DIRECTORY, MUSIC_DIRECTORY)


class SteamApp:
    """Represents a single Steam application.

    It's a collection of unique `AppManifest` associated with a path to the Steam
    library. Additional `AppManifest` can be added to the `SteamApp` if they share the
    same install directory.

    The constructor will raise `FileNotFoundError` if the `manifest` or `steam_library`
    point to non-existent install directory.

    :param steam_library: Path to the Steam library.
    :param manifest: `AppManifest` for the application.
    """

    _hash_function: str = hashlib.sha256().name

    def __init__(self, steam_library: Path, manifest: AppManifest) -> None:
        self._manifests = set({manifest})
        try:
            self._install_dir = Path(
                steam_games_directory(steam_library), manifest.install_dir_name
            ).resolve(True)
        except FileNotFoundError:
            self._install_dir = Path(
                steam_music_directory(steam_library), manifest.install_dir_name
            ).resolve(True)

    def add_manifest(self, manifest: AppManifest) -> None:
        if manifest.install_dir_name != self.install_dir.name:
            raise exceptions.MismatchedManifestException(
                f"The manifest's install directory '{manifest.install_dir_name}'"
                f" doesn't match the SteamApp's install directory '{self.install_dir}'"
            )
        self._manifests.add(manifest)

    @property
    def install_dir(self) -> Path:
        return self._install_dir

    @property
    def manifests(self) -> set[AppManifest]:
        return self._manifests

    @property
    def manifest_hash(self) -> str:
        """A hash of the `AppManifest`s constituting this `SteamApp`.

        This is computed by appending the content of the `AppManifest`s sorted by their
        path and then computing its SHA-256.
        """

        hasher = hashlib.new(self._hash_function)
        sorted_manifest_paths = sorted(
            manifest.manifest_path for manifest in self.manifests
        )
        for manifest_path in sorted_manifest_paths:
            hasher.update(manifest_path.read_bytes())

        return hasher.hexdigest()

    @property
    def rsync_hash(self) -> str:
        """A hash of all the install directory state of this `SteamApp`.

        This is computed as the SHA-256 hash of a tab-separated string with file paths,
        size and modification time sorted by paths with each entry separated by a
        newline. File name, size and modification time are the same criteria as used by
        rsync which has proven very well in practice.
        """

        def walk_dir(root: Path) -> list[str]:
            state: list[str] = []
            with os.scandir(root) as paths:
                for path in paths:
                    stat_result = path.stat()  # possibly cached
                    # full path, size in bytes and modification time - same as rsync
                    state.append(
                        f"{path.path}\t{stat_result.st_size}\t{stat_result.st_mtime_ns}"
                    )
                    if path.is_dir():
                        state.extend(walk_dir(Path(path.path)))

            # Cannot use in-place sort due to recursion
            return sorted(state)

        hasher = hashlib.new(self._hash_function)
        for entry in walk_dir(self.install_dir):
            hasher.update(entry.encode())

        return hasher.hexdigest()

    @property
    def content_paths(self) -> list[Path]:
        paths = [manifest.manifest_path for manifest in self.manifests]
        paths.append(self.install_dir)
        return paths

    def __repr__(self) -> str:
        return "{}({})".format(
            type(self).__name__,
            ", ".join("%s=%r" % item for item in vars(self).items()),
        )

    def __str__(self) -> str:
        return repr(self)


def get_steam_apps(steam_library: Path) -> list[SteamApp]:
    apps_by_install_dir: dict[str, SteamApp] = {}
    for manifest_path in steam_library.glob(STEAMAPPS_DIRECTORY + "/*.acf"):
        with open(manifest_path, encoding="utf-8") as manifest_file:
            logging.info("Parsing ACF file: %s", manifest_path)
            manifest = acf.load_as_app_manifest(manifest_file)
            logging.debug("Parsed ACF file '%s' as: %s", manifest_path, manifest)

            if manifest.app_id in INSTALL_DIR_OVERRIDES:
                overriden_install_dir = INSTALL_DIR_OVERRIDES[manifest.app_id]
                logging.info(
                    "Overriding install dir of app id '%s' from '%s' to '%s'",
                    manifest.app_id,
                    manifest.install_dir_name,
                    overriden_install_dir,
                )
                manifest = manifest._replace(install_dir_name=overriden_install_dir)

            if manifest.install_dir_name not in apps_by_install_dir:
                app = SteamApp(steam_library, manifest)
                apps_by_install_dir[manifest.install_dir_name] = app
                logging.debug("Created new SteamApp: %s", app)
            else:
                apps_by_install_dir[manifest.install_dir_name].add_manifest(manifest)
                logging.debug(
                    "Added manifest %s to %s",
                    manifest,
                    apps_by_install_dir[manifest.install_dir_name],
                )

    return list(apps_by_install_dir.values())


def verify_all_apps_discovered(app_count: int, steam_library: Path) -> None:
    """Verify that number of discovered apps matches the number of install directories.

    :param app_count: Number of apps discovered.
    :param steam_library: Path to Steam library.
    :raises RuntimeError: If `app_count` doesn't match the number of top-level
        directories under the `steam_library`'s "common" and "music" subdirectories.
    """
    games_count = len(
        [
            path
            for path in steam_games_directory(steam_library).iterdir()
            if path.is_dir()
        ]
    )
    music_count = len(
        [
            path
            for path in steam_music_directory(steam_library).iterdir()
            if path.is_dir()
        ]
    )
    total_count = games_count + music_count
    overrides_count = len(INSTALL_DIR_OVERRIDES)
    logging.debug(
        "Total apps: %s (games=%s, music=%s). Discovered apps: %s and %s overrides",
        total_count,
        games_count,
        music_count,
        app_count,
        overrides_count,
    )
    if total_count != app_count + overrides_count:
        raise RuntimeError(
            f"Expected number of apps ({app_count}) to match number of install"
            f" directories ({total_count}) excluding overrides"
            f" ({len(INSTALL_DIR_OVERRIDES)})"
        )


def run() -> None:
    args: Arguments = parse_arguments()
    logging.info(
        "Will %s Steam library backup from '%s' to '%s'.",
        args.mode,
        args.steam_library,
        args.destination,
    )

    apps = get_steam_apps(args.steam_library)
    verify_all_apps_discovered(len(apps), args.steam_library)

    for app in apps:

        def manifest_to_str(manifest: AppManifest) -> str:
            return (
                "AppManifest("
                + f"app_id={manifest.app_id}, "
                + f"build_id={manifest.build_id}, "
                + f"size_on_disk={manifest.size_on_disk}, "
                + f"download_size={manifest.download_size}"
                + ")"
            )

        sorted_manifests = sorted(app.manifests, key=lambda m: m.app_id)
        print(
            f"{app.install_dir};"
            + f" manifest_hash={app.manifest_hash};"
            + f" rsync_hash={app.rsync_hash};"
            + f" manifests={[manifest_to_str(manifest) for manifest in sorted_manifests]}"
        )

    # If running in overwrite mode we can avoid processing entire library if either is
    # true:
    # - buildid in archive matches buildid on disk
    # - hash of acf in archive matches hash of acf on disk


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)-8s %(message)s",
    )
    run()
