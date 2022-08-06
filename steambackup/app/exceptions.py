class MismatchedManifestException(Exception):
    """Raised when the AppManifest being added to a SteamApp doesn't have the same
    install directory as the SteamApp."""

    pass


class InvalidArgumentException(Exception):
    """Raised when an invalid argument is received."""

    pass


class VerifyException(Exception):
    """Raised when a condition that is expected to be true is not."""

    pass
