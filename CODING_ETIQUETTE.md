# Coding Etiquette — Claude Code

A non-comprehensive list of conventions. Rules are concrete and enforceable. 

## Naming

- Names must describe what the thing represents, not how it's used. Keep variable names to 3 words max.
- Distinguish singular vs. collection in the name (`apple` vs `apples`).
- No single letters except conventional math/loop indices (`i`; `k`).
- Booleans read as predicates: `is_pineapple`, `has_money`, `did_this`.

## Structure & duplication

- Don't duplicate logic. If the same computation appears twice, extract one function.
- One function does one thing. A function that both computes a baseline and writes somewhere is two functions.
- When possible, break the project into sections that can be unit tested. 

## Consistency

- One way to do each thing across the codebase: pick pandas vs numpy idioms, log-space vs linear conventions, etc., and stay consistent.
- Consistent units and conventions.
- Consistent parameter naming (`alpha`, `q`, `constant`).

## Correctness & clarity

- Prefer the why. Add a what only when the code can't be made self-explanatory through naming or extraction. Don't write comments that merely restate the syntax.
- Never use magic numbers. Name them: `CONST = 10`.
- Fail loudly on violated assumptions rather than silently producing garbage.

## Hygiene

- No dead code, no commented-out blocks left behind, no unused imports.
- Every function that makes a keep/drop decision should be traceable for the ledger. Don't bury decisions inside comprehensions where they can't be instrumented.
- Avoid putting historical references in documentation or in code comments unless absolutely necessary. No code history lessons (used to be X, now Y) unless they serve a real, justifiable purpose, or explain an important design decision, in which case you should write a short, concise 1-2 sentence max explanation.
- Renaming or removing a field/term is a full sweep, not an edit at the call site: `grep` code and docs for every reference and update all of them. Never leave a removed term visible for context ("renamed from X", "no longer Y") in docs or comments.
