# AXI CLI Exit Codes
#
# Standard exit codes for CI/CD integration.
# AXI is STRICT: any failure returns non-zero.
#
# - 0: SUCCESS - All items processed without error
# - 1: GENERAL_ERROR - Unexpected runtime failure
# - 2: CONFIG_ERROR - Invalid configuration (axi.yml, env vars)
# - 3: VALIDATION_ERROR - Invalid input (bad SQL syntax, schema violations)
# - 4: NOT_FOUND - Required resource not found
# - 5: EXTRACTION_ERROR - One or more items failed during extraction
#      This includes partial success scenarios (some items ok, some failed)
#      CI/CD should treat exit 5 as failure - data may be incomplete
# - 6: CONNECTION_ERROR - Database/warehouse connection failed

SUCCESS = 0
GENERAL_ERROR = 1
CONFIG_ERROR = 2
VALIDATION_ERROR = 3
NOT_FOUND = 4
EXTRACTION_ERROR = 5  # Includes partial failures - never trust partial data
CONNECTION_ERROR = 6
