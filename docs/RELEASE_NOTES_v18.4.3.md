# TV Manager 18.4.3 — Cached scene-number mappings

Refresh Scene Mapping on Show Detail/Library downloads XEM mappings using the show TVDB ID. Metadata refresh automatically refreshes mappings for scene-enabled shows at most once daily after a successful refresh. Cached mappings are separate from manual episode overrides; search and completed-file matching consult them. Reverse matching supports a scene file linked to several canonical episodes. Library mapping lists identify XEM versus manual entries.

Failed external refresh preserves existing mappings. A public XEM sample request returned HTTP 403 from this environment: live service compatibility is unverified. Tests cover forward/reverse lookup, cache reuse, manual precedence, multi-mapping payloads and invalid responses. One-to-many forward search uses the first scene mapping; full anime alias/group behavior remains incomplete.

Validation: 286 pytest tests pass; missing-folder scanner check and compile/JavaScript syntax checks pass. Browser confirmed the scene refresh action and missing-TVDB-ID guidance against isolated QA. Production IDs, media and configuration were not changed. Restart after jobs finish for activation.

Reference: [SickChill XEM integration](https://github.com/SickChill/sickchill/blob/master/sickchill/oldbeard/scene_numbering.py). Full SickChill parity remains incomplete.
