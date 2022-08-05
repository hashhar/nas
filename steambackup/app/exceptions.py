class MismatchedManifestException(Exception):
    """Raised when the AppManifest being added to a SteamApp doesn't have the same
    install directory as the SteamApp."""

    pass
