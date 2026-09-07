# TV Manager 18.5.0 — Native TVDB search and metadata

Add Show now lets you choose TMDb or TVDB. Metadata Sources stores your TVDB API key and optional subscriber PIN, with masked readback. Shows added through TVDB retain their TVDB ID and use TVDB directly for paginated episode metadata refresh. TVDB additions offer aired or DVD episode order in the destination dialog and inherit saved show preferences.

Refresh preserves existing episode status and file location. A changed TVDB episode identity in an occupied season/episode slot stops the transaction for review. All remote episode pages are fetched before writing metadata; repeated/incomplete pagination is rejected. Login and request errors do not expose credentials. Search result text is escaped before rendering.

Existing shows keep their current provider and order. Migrating existing libraries between sources/orders, AniDB support, and broader artwork/indexer parity remain unfinished. TVDB requires operator-supplied API access; no live TVDB account was tested. Language handling accepts common two-letter locales and TVDB three-letter language codes; translation availability depends on TVDB.

Validation: 291 pytest tests passed plus focused destination checks, Python compilation and all JavaScript syntax checks. Browser checked unconfigured-TVDB guidance and a full add flow using a synthetic provider response; the saved show had TVDB ID 456, DVD order and inherited fr-FR preference. No production shows, media or credentials were changed. Restart normally after active jobs finish to activate.

Reference: [TheTVDB API](https://thetvdb.com/api-information), [official v4 OpenAPI specification](https://thetvdb.github.io/v4-api/swagger.yml). Full SickChill parity remains incomplete.
