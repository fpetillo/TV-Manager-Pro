# Responsive Layout Audit

TV Manager now uses a sidebar-aware application shell with responsive fallbacks.

## Standards

- Every page with the left navigation should use `main.shell.manager-shell`.
- Tables should live inside `.table-wrap` or be automatically wrapped by `global.js`.
- Long paths, filenames, URLs, and API errors must wrap with `overflow-wrap:anywhere`.
- Desktop screens use the fixed left sidebar.
- Smaller screens use a compact Menu button that opens the navigation overlay.
- Workflow ribbons scroll horizontally instead of stretching the page.
- Import Center and Post Processing forms collapse into one column on narrow screens.

## Pages audited

- Launchpad
- Workflow Cockpit
- Setup Assistant
- Dashboard
- Shows / Library Manager
- Library Health
- Import Center
- Post Processing
- Queue
- Upgrades
- Subtitles
- Settings
- System
- Operations
- Quality Profiles
- Routes
- Build Info
- About

## Distribution readiness note

Responsive behavior is now treated as a release requirement because this product is intended for real operator use on workstations, servers, laptops, tablets, and remote support sessions.
