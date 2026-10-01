# Hard but naturally reached derivations

The converse: complicated computations agents reliably perform when
needed. Evidence AGAINST system abstraction — do not build what the
model already does.

## 1. Formula inventory + eyeball pattern-matching (CTRL-FORMULA-LIST)

- Reach: R4=58/87 (67%). Agents constantly enumerate formulas
  (iter_rows + print + data_type checks) and visually match patterns.
- The R3 mass in FAM (36/85 print-without-comparing) is this behavior at
  work: for COPY decisions, eyeballing one exemplar's formula usually
  suffices. A computed family list would duplicate, not complement.

## 2. Input-vs-output diffing when suspicious (CHG R4=34/49)

- 69% of change footprints get a systematic agent-authored diff. Agents
  reach for `diff`/before-after comparison exactly when the situation
  smells wrong. System support here would largely re-derive what
  suspicious agents already compute; its marginal value is confined to
  the unsuspicious 31%.

## 3. Recalculation + readback (70/179 runs)

- The mechanics of verification (soffice convert, data_only reads) are
  well within agent repertoire. The system must NOT teach agents HOW to
  recalc; at most it should supply the damage SCAN they never think to run.

## 4. Manual one-hop dependency tracing (DEP R3=17)

- Agents trace precedents by hand (read formula → read referenced cells)
  whenever diagnosis requires it. Shallow, targeted, sufficient. A full
  precedent map would bury this working behavior in unneeded context.

## 5. Header eyeballing for period choice (TEMP R2 mass)

- 53/74 runs see headers without parsing; FM agents routinely hardcode
  correct period columns from visual inspection. Computed alignment adds
  value only for irregular layouts — the clean majority needs nothing.

## Lesson

Build nothing that answers questions agents already ask reliably.
The frontier is where the agent never looks (post-edit damage), not
better answers to questions it already answers (what's the formula?
what changed that I intended?).
