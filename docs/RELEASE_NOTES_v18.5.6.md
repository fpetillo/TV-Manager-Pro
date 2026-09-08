# TV Manager 18.5.6 - Plex post-processing scan workflow

Automatic refresh was enabled and both Plex servers were reachable. TV Manager show folders use UNC paths while Plex lists mapped-drive roots. The old targeting code counted each Location as a library; a single TV section with multiple roots could not be selected. Its one-location fallback could also send an invalid foreign path and unsuccessful results were not logged.

Plex discovery now deduplicates section IDs, targets matching paths with proper path boundaries, and otherwise scans TV sections without a path parameter. This lets Plex use its configured roots. Full-section scans are deduplicated per server within a processing batch. Post-processing logs scan requests and unsuccessful results. Manual full refresh reports failed/empty scans honestly. Tokens travel in headers and request failures are sanitized.

Validation: 300 pytest tests pass; Python compilation passes. Live Plex section 2 and Plex2 section 4 accepted scan requests. An immediate check did not yet show Stadium Lockup, so indexing completion is not certified. Scanning occurs after the processing batch finishes, and only when files were successfully processed and automatic refresh is enabled. Adding metadata alone does not put playable media in Plex. No media was moved for this verification.

Running app still reported 18.5.2; restart TV Manager to activate this backend change. Source publication and the one-time scan verification do not activate future automatic updates in the old process.

References: https://support.plex.tv/articles/200289306-scanning-vs-refreshing-a-library/ and https://developer.plex.tv/pms/ (library section refresh endpoint).
