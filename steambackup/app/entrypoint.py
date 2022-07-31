#!/usr/bin/env python3

import argparse
import logging
import pathlib
from typing import Any, Dict, Iterator, List, NamedTuple
import acf
import os.path

from acf import AppManifest


class Arguments(NamedTuple):
    steam_library: pathlib.Path
    destination: pathlib.Path
    mode: str


def directory_exists(arg: str) -> pathlib.Path:
    if os.path.isdir(arg):
        return pathlib.Path(arg)
    else:
        raise TypeError(f"{arg} is not a directory or does not exist")


def parse_arguments() -> Arguments:
    parser = argparse.ArgumentParser(description="Backup Steam library")
    parser.add_argument(
        "--steam-library",
        required=True,
        type=directory_exists,
        metavar="PATH",
        help=(
            "Path to the Steam library i.e. the directory containing the "
            "steamapps folder."
        ),
    )
    parser.add_argument(
        "--destination",
        required=True,
        type=directory_exists,
        metavar="PATH",
        help=(
            "Path to backup destination where archives will be created (or "
            "already exist)."
        ),
    )
    parser.add_argument(
        "--mode",
        required=True,
        metavar="MODE",
        choices=["sync", "overwrite"],
        help=(
            "sync will update archives if they exist otherwise will create "
            "new ones. overwrite will always create new archives and "
            "overwrite any existing ones."
        ),
    )
    parsed: Dict[str, Any] = vars(parser.parse_args())
    return Arguments(**parsed)


def get_manifests(steam_library: pathlib.Path) -> Iterator[AppManifest]:
    for manifest_path in steam_library.glob("steamapps/*.acf"):
        with open(manifest_path, encoding="utf-8") as manifest_file:
            yield acf.load_as_obj(manifest_file)


def group_manifests_by_install_dir(
    manifests: Iterator[AppManifest],
) -> Dict[pathlib.Path, List[AppManifest]]:
    grouped_manifests: Dict[pathlib.Path, List[AppManifest]] = {}
    for manifest in manifests:
        print(manifest.install_dir)
        grouped_manifests.setdefault(pathlib.Path(manifest.install_dir), []).append(
            manifest
        )

    return grouped_manifests


def run() -> None:
    args: Arguments = parse_arguments()
    print(group_manifests_by_install_dir(get_manifests(args.steam_library)))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
