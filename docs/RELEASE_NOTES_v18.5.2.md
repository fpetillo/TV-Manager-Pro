# TV Manager 18.5.2 - Episode search regression coverage

The reported sqlite3.Row get error originates in the running 18.3.3 episode context, which returned a raw SQLite row. The published implementation already converts this row to a dictionary (since 18.4.0). This release adds a regression exercising both search and retrieve with actual SQLite rows, provider results, result persistence, search counters and a mocked downloader handoff. No additional production-code change was needed.

Validation: 293 tests pass. No UI changes. External provider and downloader calls are mocked in this regression. The live version API reported 18.3.3 while files on disk were 18.5.1; an active post-processing job was still running. Activation requires a normal restart after processing finishes. Source publication alone does not activate the fix.
