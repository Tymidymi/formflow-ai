"""Keep existing API contract tests unauthenticated; dedicated jury tests enable it."""
import os

# Explicitly test the API contract without the independent competition gate.
# The deployed service always defaults to requiring authentication.
os.environ["FORMFLOW_AUTH_MODE"] = "off"
