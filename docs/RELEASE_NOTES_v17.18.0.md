# TV Manager v17.18.0 — Professional Navigation Center

This release reorganizes the menu system so the application feels more professional, easier to operate, and closer to a polished distributable SickChill replacement.

## Highlights

- Added a centralized shared navigation template: `templates/_nav.html`.
- Reorganized the left menu into workflow-based groups.
- Added direct access to **Logs & Events** from the main menu and quick actions.
- Added pinned quick actions for **Jobs**, **Logs**, and **Database Safety**.
- Added menu filtering with a `Filter menu…` search box.
- Added collapsible menu sections with browser-persisted state.
- Added active-section expansion so the current page is easier to understand.
- Added lightweight status badges for running jobs, error logs, and database safety.
- Improved responsive behavior for tablet and mobile menu use.

## New navigation groups

- Command Center
- Library
- Discovery & Search
- Processing
- Setup & Migration
- Administration

## Why this matters

The application now has enough screens that the old grouped menu was becoming crowded. This release turns the sidebar into an operator command center, keeping daily-use pages, troubleshooting tools, and system/safety functions easy to find.

## Compatibility

No database migration is required for this release. It is a UI/navigation and documentation release.
