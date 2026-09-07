# TV Manager 18.4.1 — Saved show defaults and library renaming

- Save These as New-Show Defaults in Edit Show Settings stores reusable quality, language, episode-status and switch preferences. Both Search and Trakt use the saved defaults; existing shows stay unchanged.
- Preview Rename on Show Detail and Library lists source/destination and associated files. Confirm selected files to rename and update episode paths, including multi-episode files.
- Renames reject existing destinations, changed previews, outside-folder files and incomplete prior operations. A cross-process file lock prevents overlap with completed-download processing. Sidecar matching requires a filename boundary so episode 1 cannot capture episode 10 subtitles.
- Filesystem failure rolls back completed moves; a durable recovery journal in rename-journals records pending/completed/rolled-back work. A crash may leave pending work requiring manual reconciliation of source/destination and DB paths; subsequent renames for that show stop until reviewed. Do not delete a pending journal before reconciliation. Empty destination folders may remain after rollback. POSIX operations require hard-link support on the same filesystem; unsupported moves fail without deleting the source.

Validation: 269 pytest tests passed; destination and post-processing focused checks passed. Isolated browser confirmed a media file plus language subtitle renamed successfully, then saved reusable defaults. Both add APIs inherited profile 4, fr-FR and subtitles disabled in the isolated library. Production media was not touched.

Full SickChill parity remains incomplete. This iteration closes saved-defaults and existing-library rename gaps. Restart normally after active jobs finish to activate backend changes and shared file-operation locking.
