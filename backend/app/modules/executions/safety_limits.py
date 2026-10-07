# ============================================================================
# Execution Safety Limits Configuration (Module 6.10)
# ============================================================================

# Maximum number of steps permissible in a single workflow definition
MAX_WORKFLOW_STEPS: int = 50

# Maximum execution run duration in seconds before timing out runaway loops
MAX_EXECUTION_DURATION_SECONDS: int = 300

# Maximum size in bytes for trigger and step mapping data payloads (500 KB)
MAX_PAYLOAD_BYTES: int = 500_000

# Maximum permitted retry attempts for failed workflow executions
MAX_RETRY_COUNT: int = 3

# Maximum permitted nested condition evaluation depth
MAX_CONDITION_DEPTH: int = 5
