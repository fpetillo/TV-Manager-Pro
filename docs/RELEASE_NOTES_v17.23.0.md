# TV Manager v17.23.0 - Show Queue Polish & Sort Accuracy

This release fixes the Show Queue Downloads sort and tightens table behavior for professional daily use.

## Fixed

- Downloads sorting now uses the real numeric downloaded episode count, not the formatted `downloaded/total` display text.
- Downloads ties sort with total episode count and completion percent so large partially downloaded shows sort predictably.
- Date columns normalize SickChill/Python ordinal dates before display, preventing values such as `737203` from showing in the queue.
- Small numeric date fragments are hidden instead of being displayed as confusing dates/IDs.

## Improved

- Numeric columns default to descending sort on first click.
- Sort indicators now show the active column and direction.
- Downloads progress bars include completed/partial/empty states and hover detail.
- Size column is right-aligned for cleaner scanning.

## Validation

- Added tests for Downloads sorting by downloaded count.
- Added tests for percent sorting, size sorting, and ordinal date normalization.
