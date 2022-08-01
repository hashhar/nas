#!/usr/bin/env python3

import argparse
import logging
from pathlib import Path
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
        self._source = Path(
            steam_library, STEAMAPPS_DIRECTORY, INSTALL_DIRECTORY_BASE, install_dir
        ).resolve()

        self._destination = backup_dir.with_name(install_dir.name).resolve()

        self._manifests: Union[List[AppManifest], None] = None

    def __str__(self) -> str:
        return " ".join(self.command)

    def add_manifest(self, manifest: AppManifest) -> None:
        if self._manifests is None:
            self._manifests = []

        self._manifests.append(manifest)
        self._destination = self._destination.with_name(
            self._destination.name + "_" + str(manifest.app_id)
        ).resolve()

    @property
    def source(self) -> Path:
        return self._source.resolve()

    @property
    def destination(self) -> Path:
        return self._destination.resolve()

    @property
    def command(self) -> List[str]:
        additional_args = [
            str(self.source.resolve()),
            str(self.destination.with_suffix(self.SEVEN_Z_SUFFIX).resolve()),
        ]
        if self._mode == MODE_SYNC:
            return self.sync_args + additional_args
        elif self._mode == MODE_OVERWRITE:
            return self.overwrite_args + additional_args
        else:
            logging.error(
                "Expected mode to be one of %s or %s", MODE_SYNC, MODE_OVERWRITE
            )
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
        logging.info("Creating job for install dir: %s", install_dir)
        job = Job(mode, steam_library, install_dir, backup_dir)
        for manifest in manifests_by_install_dir[install_dir]:
            logging.debug("Adding manifest %s to job %s", manifest, job)
            job.add_manifest(manifest)

        logging.info("Created job %s for install dir %s", job, install_dir)
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
    for job in jobs:
        logging.info(
            "Built job: %s -> %s, mode=%s, command=%s",
            job.source,
            job.destination,
            job._mode,
            " ".join(job.command),
        )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)-10s %(message)s",
    )
    run()
