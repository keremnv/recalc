# Frozen LibreOffice configuration deviation

Discovered during replay on 2026-10-01 before interpreting any full-population
outcome results. The frozen helper passes MacroExecutionMode=4; the frozen
environment incorrectly labels that as NEVER_EXECUTE. Installed UNO constants
actually resolve NEVER_EXECUTE=0 and ALWAYS_EXECUTE_NO_WARN=4. UpdateDocMode=0
correctly resolves NO_UPDATE. This is a real execution/documentation deviation
from the preregistered macro-disabled treatment; do not describe mode 4 as disabled.

The frozen spec, helper, environment and already executed artifacts are preserved.
The main replay continues with its executed configuration, not a silently changed
treatment. The frozen detector already excludes named VBA projects before LO.
The additive MACRO_CONFIG_PACKAGE_AUDIT.json audits every frozen eligible source's
package names, content types and relationship declarations for additional VBA,
XLM, scripting and macro-enabled declarations; uninspectable sources remain
unresolved. This audit alone is not proof against every arbitrary hidden payload.

At most one bounded post-primary causal follow-up is reserved to test whether
mode 0 changes recalculated values/formulas or official outcomes on a deterministic
cross-category sample. The sample and comparison will be frozen before execution,
and its results will never replace the primary treatment or original scores.
The stronger reviewer will receive this deviation at the triggered interpretation
gate. Any claims and policy recommendations must disclose the tested macro-free
scope and use the correct disabled constant in the proposed evaluation policy.
No product integration or historical rewrite is authorized by this correction.
