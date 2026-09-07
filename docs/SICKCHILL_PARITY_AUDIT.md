# SickChill Parity Audit

TV Manager v18.3.0 adds an in-app Help Center and feature parity matrix so the product can be checked against the major SickChill workflows instead of relying on scattered notes.

## Major SickChill workflow areas covered

- Add/search shows from metadata/indexers.
- Import an existing show library.
- Browse shows and episodes.
- Run wanted, backlog, and episode searches.
- Send NZB/torrent releases to a downloader or blackhole folder.
- Monitor downloader handoff and queue status.
- Post-process completed downloads.
- Rename/move/copy/link episode files.
- Audit and manage subtitles.
- Manage failed downloads.
- Bulk update episode status.
- Ignore specials or selected episodes from wanted/missing logic.
- Maintain scene exceptions and operational logs.
- Run scheduled jobs and view progress.
- Back up and protect the SQLite database.

## v18.3.0 additions

- `/help` in-app Help Center.
- `/help/sickchill-parity` conceptual guide through the Help Center.
- `/api/help` for help topics and workflow map.
- `/api/help/sickchill-parity` for the parity matrix.
- `/api/product/workflow-map` for operator workflows.
- Navigation link under Administration and footer quick actions.

## Parity status definitions

- **Complete**: TV Manager has the feature in a usable form.
- **Exists differently**: The workflow exists but uses a different TV Manager concept or screen.
- **Partial**: A foundation exists, but the workflow needs more provider-specific or automation depth.
- **Missing**: Not represented yet.
- **Better than SickChill**: TV Manager has a more guided or safer implementation.

## Current explicit improvement areas

The matrix intentionally keeps these visible:

- Search provider depth.
- Subtitle provider automation depth.
- Media-server-specific refresh/sync depth.
- Anime/scene/XEM-style edge-case parity.
- More contextual help buttons on every major form field.
