#!/usr/bin/env python3

import argparse
import logging
from pathlib import Path
import string
from typing import Any, Dict, List, NamedTuple, Union

import acf
from acf import AppManifest

STEAMAPPS_DIRECTORY = "steamapps"
INSTALL_DIRECTORY_BASE = "common"

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


def get_manifests_by_install_dir(steam_library: Path) -> Dict[Path, List[AppManifest]]:
    """
    Groups manifests by installation directory.

    Multiple manifests can have the same installation directory e.g. both 9050 and 9070
    have installdir as "Doom 3".
    """
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
    SEVEN_Z_SUFFIX = ".7z"
    common_args = [
        "/opt/7z/7zz",
        "-bs0",
        "-t7z",
        "-m0=LZMA2",
        "-mx=9",
        "-mmt=on",
        "-ssw",
        # "-mmemuse=p70" Uncomment and change if running out of memory
    ]
    overwrite_args = common_args + ["a"]
    sync_args = common_args + ["u", "-up0q0r2x1y2z1w2"]

    def __init__(
        self, mode: str, steam_library: Path, install_dir: Path, backup_dir: Path
    ):
        self._mode = mode
        # list of files to add to archive
        self._sources: List[Path] = [
            Path(
                steam_library, STEAMAPPS_DIRECTORY, INSTALL_DIRECTORY_BASE, install_dir
            )
        ]
        # path to archive
        self._destination = Path(backup_dir, install_dir.name).with_suffix(
            self.SEVEN_Z_SUFFIX
        )
        self._manifests: Union[List[AppManifest], None] = None

    def __str__(self) -> str:
        source_str = "', '".join([str(source) for source in self.sources])
        return f"{self._mode} '{source_str}' to '{self.destination}'"

    def __repr__(self) -> str:
        return self.__str__()

    def add_manifest(self, manifest: AppManifest):
        if self._manifests is None:
            self._manifests = []

        self._manifests.append(manifest)
        if manifest.manifest_path is not None:
            self._sources.append(manifest.manifest_path)
        else:
            raise RuntimeError(f"Didn't expected manifest without path: {manifest}")

    @property
    def sources(self) -> List[Path]:
        return [path.resolve() for path in self._sources]

    @property
    def destination(self) -> Path:
        return self._destination.resolve()

    @property
    def command(self) -> List[str]:
        # 7z archive.7z file1 file2 file3 ...
        additional_args = [
            str(self.destination),
            *[str(source) for source in self.sources],
        ]
        if self._mode == MODE_SYNC:
            return self.sync_args + additional_args
        elif self._mode == MODE_OVERWRITE:
            return self.overwrite_args + additional_args
        else:
            raise RuntimeError(
                f"Expected mode to be one of {MODE_SYNC} or {MODE_OVERWRITE}"
            )


def build_jobs(
    mode: str,
    steam_library: Path,
    backup_dir: Path,
    manifests_by_install_dir: Dict[Path, List[AppManifest]],
) -> List[Job]:
    jobs: List[Job] = []
    for install_dir in manifests_by_install_dir:
        logging.info("Creating job for directory: %s", install_dir)
        job = Job(mode, steam_library, install_dir, backup_dir)
        for manifest in manifests_by_install_dir[install_dir]:
            logging.debug("Adding manifest to job: %s", manifest)
            job.add_manifest(manifest)

        logging.info("Created job: %s", job)
        jobs.append(job)

    return jobs


def run() -> None:
    args: Arguments = parse_arguments()
    jobs = build_jobs(
        args.mode,
        args.steam_library,
        args.destination,
        get_manifests_by_install_dir(args.steam_library),
    )
    print(jobs)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)-8s %(name)-10s %(message)s",
    )
    run()
