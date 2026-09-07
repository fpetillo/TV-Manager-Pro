# TV Manager Navigation Center

TV Manager v17.18.0 reorganizes the left-side menu into a professional operator navigation center. The goal is to make the application feel like a distributable product instead of a collection of separate pages.

## Operator quick actions

The top of the menu now includes direct quick links for the screens that matter during real use:

- **Jobs** — monitor background work and progress bars.
- **Logs** — open the Logs & Events viewer directly.
- **Safety** — open Database Safety for verified backups and recovery status.

These are intentionally pinned above the full menu because they are troubleshooting and operations tools that need to be available from every screen.

## Reorganized sections

The menu is now grouped by workflow:

- **Command Center** — Launchpad, Dashboard, Workflow Cockpit, Active Jobs, Logs & Events.
- **Library** — Show Queue, Shows, Manage Center, Library Health, Upcoming, Missing.
- **Discovery & Search** — Add/Search Show, Trakt Discover, Download Queue, Upgrades.
- **Processing** — Post Processing, Subtitles, Quality Profiles, Operations.
- **Setup & Migration** — Setup Assistant, SickChill Import, Advanced.
- **Administration** — Settings, Database Safety, System, Build Info, Routes, About.

## Menu filtering

The menu includes a `Filter menu…` box. Operators can type words such as `log`, `job`, `post`, `backup`, `trakt`, or `show` and the menu narrows to matching pages.

## Collapsible sections

Menu sections can collapse and expand. The currently active section opens automatically so the operator does not lose context. Collapsed state is saved in the browser using local storage.

## Status badges

The menu can show lightweight status badges for:

- running jobs
- recent error logs
- database safety status

These checks are non-blocking and fail quietly when a page or API is unavailable.

## Shared navigation template

Navigation is now centralized in `templates/_nav.html`. Pages include that template instead of carrying their own duplicated menu HTML. This makes future menu changes safer and keeps every page consistent.
