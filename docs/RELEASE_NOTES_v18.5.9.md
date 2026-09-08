# TV Manager 18.5.9 - Edit show names

Edit Show Settings includes a Show name field. Save trims and validates the title (1-250 characters, no control characters), updates the existing show record and reloads the page. Titles are excluded from reusable new-show defaults. A custom name override keeps TMDb and TVDB metadata refreshes from replacing the corrected title. Existing folders, episode paths and metadata IDs are unchanged; future searches/naming use the corrected show name according to existing alias/preferences rules.

Validation: 301 tests pass; Python compile and JavaScript syntax pass. Regression validates custom names and default exclusion, and TVDB refresh retains an overridden title. Isolated browser renamed Parity Test Show to Corrected QA Show and verified updated heading. No production shows were renamed. UI readback detects older servers that ignore the new field and requests a restart instead of reporting success.

Restart required to add the name_override column and activate the updated backend. Then open Show Detail > Edit Show Settings > Show name > Save Show Settings.
