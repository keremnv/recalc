"""Live-run bootstrap; loaded only through the experiment's PYTHONPATH."""

# candidate_a_live_runtime invokes its installer once at module import.  Do
# not call it a second time here: Python imports sitecustomize exactly once per
# interpreter, and double installation would wrap fallback recursively.
import benchmark.candidate_a_live_runtime  # noqa: F401
