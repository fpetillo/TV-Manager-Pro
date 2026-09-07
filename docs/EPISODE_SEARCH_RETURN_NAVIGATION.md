# Episode Search Return Navigation

TV Manager v17.21.0 improves the show detail workflow after an episode search result is sent to the configured downloader.

## Behavior

When an operator opens a show, searches an episode, and sends a result to the downloader, TV Manager now:

1. keeps the current show detail page context,
2. remembers the episode list scroll/filter/page position,
3. runs the downloader handoff as a monitored background job,
4. closes the search modal after a successful handoff,
5. refreshes the episode list, and
6. returns the operator to the same episode list workflow.

A **Back to Episodes** button is also available inside the search modal so the operator is never trapped after reviewing results.

## Related pages

- Show Detail: `/show/<show_id>`
- Download Center: `/download-center`
- Active Jobs: `/jobs`
- Logs & Events: `/logs`
