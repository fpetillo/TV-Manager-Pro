# TV Manager v17.10.0 - Responsive Fit & Distribution Polish

This release focuses on making the left-navigation product shell fit correctly across desktop, laptop, tablet, and narrow browser sizes.

## Highlights

- Import Center now uses the same `manager-shell` layout as the rest of the sidebar-era application.
- Home/search page now uses the sidebar-aware layout.
- Added mobile navigation toggle for small screens instead of forcing the full sidebar into the content area.
- Added automatic table wrapping for legacy screens that still render plain tables.
- Improved wide path handling for import, post-processing, metadata, system, and diagnostics screens.
- Strengthened progress display styles for the Import Center background job.
- Improved responsive form grids, action toolbars, page cards, command palette, workflow ribbon, and table overflow behavior.

## Operator impact

Large libraries, long filesystem paths, and migration/post-processing tables should no longer force the entire screen sideways. Operators should be able to use Import Center, Post Processing, Library Health, Settings, System, and Manager screens from normal desktop windows and smaller laptop/tablet windows.
