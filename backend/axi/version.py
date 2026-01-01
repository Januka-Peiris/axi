# Licensed under the Business Source License 1.1 (BSL).
# Usage and rights governed by backend/LICENSE.
# Change Date: 2027-01-01. Change License: MIT.

"""
Lightweight version helpers so CLI/API can expose consistent package versions.
"""

from importlib import metadata

# Keep this in sync with backend/pyproject.toml
__version__ = "0.1.0"

# Metadata schema version - bump when breaking changes to metadata format
# Format: MAJOR.MINOR (no patch - schema changes are either breaking or additive)
# MAJOR: Breaking changes that require migration
# MINOR: Additive changes (new optional fields)
SCHEMA_VERSION = "1.0"


def get_version() -> str:
    """
    Return the installed backend package version if available,
    otherwise fall back to the source constant.
    """
    try:
        return metadata.version("axi-semantic")
    except metadata.PackageNotFoundError:
        return __version__
