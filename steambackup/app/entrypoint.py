#!/usr/bin/env python3

import argparse
import logging
import os.path
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, NamedTuple

import humanize

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
        if os.path.exists(arg) and os.path.isdir(arg):
            return Path(arg)
        else:
            raise TypeError(f"{arg} is not a directory or does not exist")

    def is_steam_library(arg: str) -> Path:
        path = Path(arg, STEAMAPPS_DIRECTORY)
        if os.path.exists(path) and os.path.isdir(path):
            return Path(arg)
        else:
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


def get_manifests(steam_library: Path) -> List[AppManifest]:
    manifests: List[AppManifest] = []
    for manifest_path in steam_library.glob("steamapps/*.acf"):
        with open(manifest_path, encoding="utf-8") as manifest_file:
            manifests.append(acf.load_as_obj(manifest_file))

    return manifests


def group_manifests_by_install_dir(
    steam_library: Path,
    manifests: List[AppManifest],
) -> Dict[Path, List[AppManifest]]:
    grouped_manifests: Dict[Path, List[AppManifest]] = {}
    for manifest in manifests:
        grouped_manifests.setdefault(
            Path(
                steam_library,
                STEAMAPPS_DIRECTORY,
                INSTALL_DIRECTORY_BASE,
                manifest.install_dir,
            ),
            [],
        ).append(manifest)

    return grouped_manifests


def run() -> None:
    args: Arguments = parse_arguments()
    start = datetime.utcnow()
    print(
        group_manifests_by_install_dir(
            args.steam_library, get_manifests(args.steam_library)
        )
    )
    print(humanize.precisedelta(datetime.utcnow() - start))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
