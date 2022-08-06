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
    def directory_exists(arg: str) -> Path:
        path = Path(arg)
        if path.exists() and path.is_dir():
            return path.resolve(True)
        else:
            logging.error("%s is not a dictionary or does not exist", arg)
            raise TypeError()

    def is_steam_library(arg: str) -> Path:
        steamapps_path = Path(arg, STEAMAPPS_DIRECTORY)
        if steamapps_path.exists() and steamapps_path.is_dir():
            return Path(arg).resolve(True)
        else:
            logging.error(
                "%s does not have a %s directory or does not exist",
                arg,
                STEAMAPPS_DIRECTORY,
            )
            raise TypeError()

    parser = argparse.ArgumentParser(description="Backup Steam library")
    parser.add_argument(
        "--steam-library",
        required=True,
        type=is_steam_library,
        metavar="PATH",
        help="Path to the Steam library i.e. the directory containing the steamapps folder.",
    )
    parser.add_argument(
        "--destination",
        required=True,
        type=directory_exists,
        metavar="PATH",
        help="Path to backup destination where archives will be created (or already exist).",
    )
    parser.add_argument(
        "--mode",
        required=True,
        metavar="MODE",
        choices=[MODE_SYNC, MODE_OVERWRITE],
        help=(
            "sync will update archives if they exist otherwise will create new ones."
            "overwrite will always create new archives and overwrite any existing ones."
        ),
    )
    parsed: dict[str, Any] = vars(parser.parse_args())
    return Arguments(**parsed)


def steam_games_directory(steam_library: Path) -> Path:
    return Path(steam_library, STEAMAPPS_DIRECTORY, COMMON_DIRECTORY)


def steam_music_directory(steam_library: Path) -> Path:
    return Path(steam_library, STEAMAPPS_DIRECTORY, MUSIC_DIRECTORY)


class SteamApp:
    """Represents a single Steam application.

    It's a collection of unique `AppManifest` associated with a path to the Steam
    library. Additional `AppManifest` can be added in case they share the same install
    directory.

    This may raise errors during construction if the `manifest` or `steam_library` point
    to non-existent install directory.

    :param steam_library: Path to the Steam library.
    :param manifest: `AppManifest` for the application.
    """

    _hash_function: str = hashlib.sha256().name

    def __init__(self, steam_library: Path, manifest: AppManifest) -> None:
        self._manifests = set({manifest})
        try:
            self._install_dir = Path(
                steam_games_directory(steam_library),
                manifest.install_dir_name,
            ).resolve(True)
        except FileNotFoundError:
            self._install_dir = Path(
                steam_music_directory(steam_library),
                manifest.install_dir_name,
            ).resolve(True)

    def add_manifest(self, manifest: AppManifest) -> None:
        """Add additional `AppManifest` to the `SteamApp`.

        This has no effect if the `manifest` already exists in the `SteamApp`.

        :param manifest: `AppManifest` to add to the `SteamApp`.
        :raises MismatchedManifestException: If the `manifest`'s install directory
            doesn't match the `SteamApp` install directory.
        """
        if manifest.install_dir_name != self.install_dir.name:
            raise exceptions.MismatchedManifestException(
                f"The manifest's install directory '{manifest.install_dir_name}' "
                "doesn't match the SteamApp's install directory '{self.install_dir}'"
            )
        self._manifests.add(manifest)

    @property
    def install_dir(self) -> Path:
        """Absolute path to the install directory."""
        return self._install_dir

    @property
    def manifests(self) -> set[AppManifest]:
        """Set of `AppManifest`s which constitute this `SteamApp`."""
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
                    # full path, size in bytes and modification time - same as what rsync checks
                    state.append(
                        f"{path.path}\t{stat_result.st_size}\t{stat_result.st_mtime_ns}"
                    )
                    if path.is_dir():
                        state.extend(walk_dir(Path(path.path)))

            return sorted(state)

        hasher = hashlib.new(self._hash_function)
        if self.install_dir is not None:
            for entry in walk_dir(self.install_dir):
                hasher.update(entry.encode())

        return hasher.hexdigest()

    @property
    def content_paths(self) -> list[Path]:
        """List of paths which contain content for this `SteamApp`.

        The paths include all the manifest files and the install directory.
        """
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
    """Get list of `SteamApp`s discovered in the `steam_library`.

    :param steam_library: Path to Steam library.
    :return: List of discovered `SteamApp`s.
    """
    apps_by_install_dir: dict[str, SteamApp] = {}
    for manifest_path in steam_library.glob(STEAMAPPS_DIRECTORY + "/*.acf"):
        with open(manifest_path, encoding="utf-8") as manifest_file:
            logging.info("Parsing ACF file: %s", manifest_path)
            manifest = acf.load_as_app_manifest(manifest_file)
            logging.debug("Parsed ACF file %s as: %s", manifest_path, manifest)

            if manifest.app_id in INSTALL_DIR_OVERRIDES:
                logging.info(
                    "Overriding install dir from ACF file %s with %s",
                    manifest_path,
                    INSTALL_DIR_OVERRIDES[manifest.app_id],
                )
                manifest._replace(install_dir=INSTALL_DIR_OVERRIDES[manifest.app_id])

            if manifest.install_dir_name not in apps_by_install_dir:
                apps_by_install_dir[manifest.install_dir_name] = SteamApp(
                    steam_library, manifest
                )
            else:
                apps_by_install_dir[manifest.install_dir_name].add_manifest(manifest)

    return [steam_app for steam_app in apps_by_install_dir.values()]


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
    if total_count != app_count + len(IGNORED_APP_IDS):
        raise RuntimeError(
            f"Expected number of apps ({app_count}) and number of install directories"
            "({total_count}) to match excluding ingored app count"
        )


def run() -> None:
    args: Arguments = parse_arguments()
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

        print(
            f"{app.install_dir};"
            + f" manifest_hash={app.manifest_hash};"
            + f" rsync_hash={app.rsync_hash};"
            + f" manifests={[manifest_to_str(manifest) for manifest in app.manifests]}"
        )

    # If running in overwrite mode we can avoid processing entire library if either is
    # true:
    # - buildid in archive matches buildid on disk
    # - hash of acf in archive matches hash of acf on disk


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(name)-10s %(message)s",
    )
    run()
