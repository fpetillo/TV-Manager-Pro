# TV Manager 18.5.3 - Show Detail initial load

Opening a show could remain on Loading until the episode Refresh button was pressed. A missing JavaScript statement separator chained the page initializer onto the preceding downloader-handler assignment. This invoked that handler before its modal existed and prevented startup from scheduling show and episode requests.

Added the explicit separator. A Node VM regression executes the actual page script and verifies that startup schedules both reads without invoking the downloader. The regression fails on the old script and passes on the corrected script. Existing request timeouts are unchanged.

Validation: 294 pytest tests pass, JavaScript syntax passes. Browser reproduced the startup errors on live 18.5.2, then opening Friends from Show Queue after the static fix loaded the header and first 50 episodes without pressing Refresh. No media or settings changed. The corrected static script is served by the current process; reopen Show Detail to load it. A normal server restart is still needed for the runtime version label to become 18.5.3.
