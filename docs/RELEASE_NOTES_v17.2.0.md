# TV Manager v17.2.0 Release Notes

v17.2.0 advances TV Manager toward a complete SickChill replacement package.

## Added

- Full SickChill server replacement runbook.
- Production Linux deployment guide.
- Linux systemd installer script.
- Read-only server preflight checker for SickChill database, media roots, Python/Git availability, and port conflicts.
- Documentation validation tests to ensure replacement docs and scripts stay packaged.

## Operator focus

This release emphasizes production readiness: install beside SickChill, import from a database copy, verify Library Health, then cut over safely with rollback instructions.
