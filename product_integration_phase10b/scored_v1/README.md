# Diagnostic Phase-10B v1 score

The initial arm runs passed correctness, but their experimental sitecustomize modules lacked precompiled bytecode while the installed production sitecustomize had cached bytecode. This invalidates fine import-cost attribution. All rows are preserved; a fully rerun normalized score is required.
