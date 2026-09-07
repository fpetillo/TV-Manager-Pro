# TV Manager v18.2.1 - Show Load Progress Polish

This maintenance polish release closes the visible gap where opening/loading a show could leave the operator waiting without a progress indicator.

## Changes

- Show Queue now displays a floating "Loading show" progress indicator when a show is opened.
- Show Detail now displays a progress panel while show metadata, season counts, and ignored episode rules load.
- Episode lists now render a progress row while filters, paging, or refreshes are loading.
- Added an indeterminate progress animation for operations whose exact percent is not available.

## Validation

- Static UI contract tests verify the new progress elements and navigation loading hooks.
