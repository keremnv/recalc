# Pilot validation (before protocol freeze)

Pilot identities/selection are in PILOT_MANIFEST.json. No materiality thresholds
were tuned. Pre-plumbing logs are preserved in pilot_preplumbing. The corrected
pilot is in pilot. Known Phase12 06_05 CONTROL verifies formula/cache identity,
cache-only sufficiency and scorer plumbing; its TREATMENT verifies the no-effect
path. Lexical formula-error/no-formula/complex FM selections validate input/package
parsing and unsupported policy. The first complex FM contains volatile functions;
an additional lexical supported complex FM validates the actual recalc/export path.

Seven mechanical unit tests passed before the full replay. Typed numeric/string,
empty/string-missing distinction, error/Boolean caches, shared-string decoding,
formula-literal/reference preservation, no-op witness, and unrelated literal
change rejection passed. UNO isolation uses hash-unique pipes and fresh profiles.
Iteration-enabled archives are replayed but cannot receive strong attribution;
this pre-freeze amendment preserves settings and handles ambiguity explicitly.

Nothing in this pilot supports a new historical conclusion. It is plumbing only.
