# TV Manager UI Design System

TV Manager uses a professional dark operations-console design intended for long-running local and server deployments.

## Principles

1. **Operator clarity** — every page should show what it does and what action is safe to take next.
2. **Safe by default** — destructive workflows use preview/apply patterns and audit language.
3. **Cohesive shell** — navigation, page headers, cards, buttons, forms and tables should look consistent.
4. **Version visible** — every support screenshot should make the running version easy to identify.
5. **Migration confidence** — SickChill replacement workflows should clearly separate analyze, preview, import, validate and cutover.

## Core surfaces

- **Dashboard:** command center for health, automation, recent work and downloads.
- **Shows:** professional library console for finding shows and reviewing seasons.
- **Import Center:** migration workflow for SickChill replacement.
- **Library Health:** operational quality gate after migration and before cutover.
- **System/About:** version, runtime, route and deployment verification.

## Styling conventions

- Use `.panel` for major content regions.
- Use `.product-hero` for page-level context and primary outcomes.
- Use `.product-badge` for concise operational labels.
- Use `.section-kicker` to create consistent section hierarchy.
- Keep buttons action-oriented: Analyze, Preview, Import, Validate, Repair, Download.
