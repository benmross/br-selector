"""Profile build only (tools/build_cmp_profile.sh puts this directory on
PYTHONPATH): install the comparison probe before anything imports sqlglot, in
pytest, its xdist workers and any Python subprocess a test starts."""
import os

if os.environ.get("CMP_PROFILE_OUT"):
    import cmp_profile
    import inprocess  # noqa: F401  (process pools run inline, as in the map build)

    cmp_profile.install(os.environ["CMP_PROFILE_ROOT"], os.environ["CMP_PROFILE_OUT"])
