#!/usr/bin/env python3

import argparse
import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Union

import acf
from acf import AppManifest

STEAMAPPS_DIRECTORY = "steamapps"
COMMON_DIRECTORY = "common"

MODE_SYNC = "sync"
MODE_OVERWRITE = "overwrite"


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
    parsed: Dict[str, Any] = vars(parser.parse_args())
    return Arguments(**parsed)


def resolve_install_dir(steam_library: Path, install_dir: str) -> Path:
    return Path(
        steam_library, STEAMAPPS_DIRECTORY, COMMON_DIRECTORY, install_dir
    ).resolve(True)


class SteamApp:
    _hash_function: str = hashlib.sha256().name

    def __init__(self, steam_library: Path):
        self._steam_library = steam_library
        self._install_dir: Union[Path, None] = None
        self._manifests: List[AppManifest] = []

    def add_manifest(self, manifest: AppManifest):
        if self.install_dir is None:
            self._install_dir = resolve_install_dir(
                self._steam_library, manifest.install_dir
            )
        self._manifests.append(manifest)

    @property
    def install_dir(self):
        if self._manifests is None:
            raise RuntimeError("No manifests are added to the SteamApp yet")

        return self._install_dir

    @property
    def manifests(self):
        return self._manifests

    @property
    def manifest_hash(self) -> str:
        hasher = hashlib.new(self._hash_function)
        sorted_manifest_paths = sorted(
            manifest.manifest_path for manifest in self.manifests
        )
        for manifest_path in sorted_manifest_paths:
            hasher.update(manifest_path.read_bytes())

        return hasher.hexdigest()

    @property
    def rsync_hash(self) -> str:
        def walk_dir(root: Path) -> List[str]:
            state: List[str] = []
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

    def __repr__(self):
        return "%s(%s)" % (
            type(self).__name__,
            ", ".join("%s=%r" % item for item in vars(self).items()),
        )


def get_steam_apps(steam_library: Path) -> List[SteamApp]:
    apps_by_install_dir: Dict[Path, SteamApp] = {}
    for manifest_path in steam_library.glob(STEAMAPPS_DIRECTORY + "/*.acf"):
        with open(manifest_path, encoding="utf-8") as manifest_file:
            logging.info("Parsing ACF file: %s", manifest_path)
            manifest = acf.load_as_app_manifest(manifest_file)
            logging.debug("Parsed ACF file %s as: %s", manifest_path, manifest)
            apps_by_install_dir.setdefault(
                resolve_install_dir(steam_library, manifest.install_dir),
                SteamApp(steam_library),
            ).add_manifest(manifest)

    return [steam_app for steam_app in apps_by_install_dir.values()]


def verify_all_apps_discovered(app_count: int, steam_library: Path):
    # Verify that number of discovered apps matches the number of install directories
    install_dir_count = len(
        [
            path
            for path in Path(
                steam_library, STEAMAPPS_DIRECTORY, COMMON_DIRECTORY
            ).iterdir()
            if path.is_dir()
        ]
    )
    if install_dir_count != app_count:
        raise RuntimeError(
            f"Expected number of apps ({app_count}) and number of install directories ({install_dir_count}) to match"
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
