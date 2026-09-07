# TV Manager v17.9.0 Release Notes

v17.9.0 improves SickChill-style post processing and responsive page fit after the left-side navigation redesign.

## Highlights

- Post Processing now has a real operator workflow for configured and override download folders.
- Added saved default completed-TV folder controls.
- Added one-time override folder support.
- Added scan limit and processing method controls.
- Added selectable preview rows with Process Selected / Process All Approved actions.
- Added `/api/postprocess/config` for reading and saving post-processing settings.
- `/api/postprocess/scan` accepts root and limit parameters.
- `/api/postprocess/run` accepts selected sources, root override, limit, and processing method.
- Added responsive layout hardening for sidebar-era pages.

## Validation

The release test suite verifies versioning, post-processing API surface, UI controls, documentation, Python compilation, and package hygiene.
