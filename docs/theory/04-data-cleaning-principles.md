# Principles of Survey Data Cleaning

Cleaning is where most of the time goes and where most of the damage is done. The tools in CPDM are shaped around a few working principles.

## Keep the raw file untouched

Every cleaning decision is reversible only if the original survives. Export from your form platform once, put that file somewhere read-only, and work on a copy. CPDM never writes over your input — it exports to `processed_<name>` — but a session has no undo, and an accidental global replacement is not something you want to reconstruct from memory.

## Record the recipe, not just the result

A cleaned spreadsheet answers "what is the data now?". It does not answer "what was done to it?". That second question turns up when a reviewer asks, when a second wave arrives, or when you return to the project after six months.

This is why CPDM records renames and replacements as a JSON recipe you can save, read and replay. A recipe is a plain-text record of your cleaning decisions: it is documentation and automation at once. It also makes waves comparable — the same rules applied identically, rather than by hand twice.

## Separate mechanical fixes from judgement calls

Two very different activities hide under "cleaning":

- **Mechanical** — stripping a translation from a header, trimming whitespace, coding *Agree* as 4. There is a right answer; apply it in bulk.
- **Judgement** — deciding that a free-text answer means "no", or that a respondent who ticked *Strongly Agree* forty times should be dropped.

Keep them apart. Bulk tools should only ever do mechanical work; anything requiring a decision should be visible, one item at a time. CPDM's ignore and exempt lists exist to draw that line — they are how you keep automatic tools off the columns where judgement is needed.

## Global replacement is powerful and blunt

Replacing text everywhere at once is the fastest way to code a questionnaire and the fastest way to corrupt it. Two failure modes recur:

- **Substring collisions.** A rule for `Agree` also matches inside `Strongly Agree`. CPDM applies longer values first to avoid that specific trap, but overlapping fragments remain your responsibility.
- **Unintended columns.** A rule meant for Likert answers also hits the same word in a free-text comment.

Both are handled the same way: exclude the columns that should not be touched *before* replacing anything, and read the counts in the log afterwards.

## Free text is not categorical data

Comment fields, names and open-ended answers look like text columns and are nothing like them. They should be excluded from every bulk operation, then handled deliberately — coded by hand, analysed separately, or left alone.

The same goes for identifiers. An ID that gets caught by a replacement rule stops linking to anything, and the breakage is silent.

## Check after every step, not at the end

A cleaning error found immediately costs a minute. The same error found after scoring costs the whole session, because there is no way back. After each step, look:

- `columns` after renaming — are the names what you intended?
- `show` after replacing — did the values change in the columns you meant?
- `summary` after scoring — are the minima and maxima inside the response range?

## Decide about attention checks before you look

Straight-lining, impossibly fast completion, contradictory answers to a reversed pair — all reasonable grounds for excluding a response, and all much less reasonable once you have seen which way excluding them moves your result. Write the rule down first, apply it mechanically, and report how many responses it removed.
