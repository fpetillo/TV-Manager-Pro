# TV Manager 18.5.4 - Collapsible season folders

Show Detail presents one collapsible section per season. All sections begin closed, with regular seasons first and Specials (S00) last. Click a season header to expand or collapse; keyboard activation is supported by native details/summary controls. A selected season filter opens that season automatically.

Episodes load only when their season opens, fetching all required pages within the season. Removed global episode pagination and page-size controls. Search/status filters apply within each season. Refresh preserves expanded sections; obsolete responses cannot replace a newer filtered view. Select Expanded selects only open-season episodes and collapsing a season clears its selection. Existing search and episode actions remain available.

Validation: 295 pytest tests pass and JavaScript syntax passes. Browser on Friends verified 11 collapsed sections, Specials last, expanding Season 1 shows all 24 episodes, collapse hides them, Select Expanded selects visible rows and collapse clears them. Regression verifies lazy loading, multi-page season retrieval, filter propagation and stale-response rejection. No episode statuses, media or settings changed during verification. Static changes verified on running app; reopen Show Detail. Runtime version label requires normal restart.
