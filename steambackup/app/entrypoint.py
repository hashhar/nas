#!/usr/bin/env python3

import argparse
import logging
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Union

import acf
from acf import AppManifest

STEAMAPPS_DIRECTORY = "steamapps"
INSTALL_DIRECTORY_BASE = "common"


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
            raise TypeError(f"{arg} is not a directory or does not exist")

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
            raise TypeError(
                f"{arg} does not have a {STEAMAPPS_DIRECTORY} directory or does not exist"
            )

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
        choices=["sync", "overwrite"],
        help=(
            "sync will update archives if they exist otherwise will create new ones."
            "overwrite will always create new archives and overwrite any existing ones."
        ),
    )
    parsed: Dict[str, Any] = vars(parser.parse_args())
    return Arguments(**parsed)


def get_manifests_by_install_dir(steam_library: Path) -> Dict[Path, List[AppManifest]]:
    manifests_by_install_dir: Dict[Path, List[AppManifest]] = {}
    for manifest_path in steam_library.glob(STEAMAPPS_DIRECTORY + "/*.acf"):
        with open(manifest_path, encoding="utf-8") as manifest_file:
            logging.info("Parsing ACF file: %s", manifest_path)
            manifest = acf.load_as_obj(manifest_file)
            logging.debug("Parsed ACF file %s as: %s", manifest_path, manifest)
            manifests_by_install_dir.setdefault(Path(manifest.install_dir), []).append(
                manifest
            )

    return manifests_by_install_dir


class Job:
    def __init__(self, steam_library: Path, install_dir: Path, backup_dir: Path):
        self._source = Path(
            steam_library, STEAMAPPS_DIRECTORY, INSTALL_DIRECTORY_BASE, install_dir
        )

        self._backup_dir = backup_dir
        self._install_dir_name = install_dir.name

        self._manifests: Union[List[AppManifest], None] = None
        return self

    def add_manifest(self, manifest: AppManifest):
        if self._manifests is None:
            self._manifests = []

        self._manifests.append(manifest)

    @property
    def destination(self):
        backup_dir = self._backup_dir
        file_name = self._install_dir_name
        if self._manifests is None:
            raise RuntimeError("Expected at-least 1 manifest to exist")

        for manifest in self._manifests:
            file_name += "_" + str(manifest.app_id)

        return Path(backup_dir, file_name)


def run() -> None:
    args: Arguments = parse_arguments()
    print(args)
    print(
        get_manifests_by_install_dir(args.steam_library),
        args.destination,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(name)-10s %(message)s",
    )
    run()
