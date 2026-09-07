# TV Manager v17.8.0 Release Notes

This release focuses on large-library performance and operator scale.

## Fixed

- Fixed the Shows / Library page appearing stuck at `Showing...` after importing very large SickChill databases.
- `/api/shows` no longer returns the entire library by default.

## Added

- Server-side pagination for `/api/shows`.
- Response metadata: `total`, `limit`, `offset`, `next_offset`, and `has_more`.
- Load-more workflow in the Library UI.
- Better error handling when the Library API returns HTML or server errors.
- Additional database indexes for large installs.

## Operator impact

Large imports, including libraries with tens of thousands of rows, should open much faster and remain responsive.
