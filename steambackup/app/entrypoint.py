#!/usr/bin/env python3

import argparse
import hashlib
import logging
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
            return path
        else:
            logging.error("%s is not a dictionary or does not exist", arg)
            raise TypeError()

    def is_steam_library(arg: str) -> Path:
        steamapps_path = Path(arg, STEAMAPPS_DIRECTORY)
        if steamapps_path.exists() and steamapps_path.is_dir():
            return Path(arg)
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


class SteamApp:
    def __init__(self):
        self._manifests: List[AppManifest] = []

    def add_manifest(self, manifest: AppManifest):
        self._manifests.append(manifest)

    @property
    def manifests(self):
        return self._manifests

    @property
    def sha256(self) -> bytes:
        hasher = hashlib.sha256()
        sorted_manifest_paths = sorted(
            manifest.manifest_path for manifest in self.manifests
        )
        for manifest_path in sorted_manifest_paths:
            hasher.update(manifest_path.read_bytes())

        return hasher.digest()

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
                Path(manifest.install_dir), SteamApp()
            ).add_manifest(manifest)

    return [steam_app for steam_app in apps_by_install_dir.values()]


def run() -> None:
    args: Arguments = parse_arguments()
    apps = get_steam_apps(args.steam_library)
    print(apps)

    print(apps[0].manifests, apps[0].sha256)

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
