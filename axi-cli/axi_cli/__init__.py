# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

from importlib import metadata

# Keep in sync with axi-cli/pyproject.toml
__version__ = "0.1.0"


def get_version() -> str:
    try:
        return metadata.version("axi-cli")
    except metadata.PackageNotFoundError:
        return __version__
