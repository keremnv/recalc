# Contributing / development loop

1. Pick one failing benchmark task.
2. Reproduce the failure with the current MCP surface.
3. Classify it:
   - model reasoning failure,
   - missing inspection semantic,
   - missing write semantic,
   - inefficient interaction requiring program execution,
   - validation/dynamic-correctness failure.
4. Add the narrowest reusable abstraction that addresses the class of failure.
5. Add an in-memory/backend-level regression test.
6. Re-run the task and record score + tool-call/token deltas.

Avoid designing the complete agent spreadsheet language up front. Let observed failure modes grow it.
