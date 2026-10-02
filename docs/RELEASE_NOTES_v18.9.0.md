# TV Manager v18.9.0 — Download resolution preferences

Set the desired download resolution for one show, selected shows, a saved show group, every show in the library, or newly added shows. Choices are SD (480p / 576p), 720p, 1080p, 2160p / 4K, and Use quality profile.

## Set the whole library to 1080p

1. Open Shows or Show Queue and choose **Set Resolution** in the Download resolution panel.
2. Choose **All shows**, then **1080p**.
3. Optionally check **Also use this as the default for newly added shows**.
4. Choose **Review Change**, review the show count, then confirm.

All shows means the entire library, including shows beyond the visible page or filter. For a custom selection, check the show rows first; selections persist across pages and filters on that page. Use the saved-group scope for an existing show group. New shows only changes the default without changing existing shows.

For one show, open **Edit Show Settings → Download resolution → Save Show Settings**. The same preference is available when adding a show and editing new-show defaults. Choosing Use quality profile restores that show's existing profile resolution behavior.

## Search and existing files

A fixed resolution overrides the quality profile's minimum/maximum resolution only. Codec restrictions, required/ignored/preferred words, the assigned profile and its upgrade-enabled setting remain in effect. 1080p means 1080p: 720p, 1080i, 2160p and unknown-resolution releases are rejected. Resolution detection uses release titles, so poorly labeled releases may need a better-labeled result.

Episode searches, automatic grabs and season-pack searches honor the choice. Cached search results are checked against current settings again before downloader handoff. An accept rule cannot bypass a fixed resolution. Search again after changing preferences to refresh previously rejected results.

Saving the preference does not start downloads, transcode or move media, mark episodes missing, or replace existing files. Lower-resolution downloaded episodes can be reviewed through Upgrades; higher-resolution existing files are retained. Newly added shows inherit the saved default; changing the default alone does not retroactively change existing shows.

Bulk review expires after 15 minutes. Changed show membership, preferences or relevant defaults require a fresh review. Writes are atomic and preserve unrelated show/default settings. The additive schema migration starts existing shows with their previous quality-profile behavior.

## Validation and activation

- 417 tests passed; two existing live symbolic-link tests skipped because this Windows account lacks OS permission.
- All 65 top-level Python modules and 40 JavaScript files pass syntax checks; dependency consistency passes.
- Regression coverage includes 1,204-show updates, group/selected/all/default-only scopes, stale reviews, tampered tokens, CSRF, exact-resolution filtering, upgrade planning, cached episode/season-pack rejection and preservation of recorded files/statuses.
- Browser checks in an isolated 105-show library verified selected/group/all saves, default persistence, selection across queue pages and single-show save/reopen. The compact review dialog keeps confirmation reachable. No browser console errors.
- No production preferences, media or downloads were changed by testing. No real downloader request, new executable build, Inno installer build or target-server deployment is claimed.

Update the source installation to v18.9.0, restart TV Manager normally and refresh browser pages. VERSION, release manifest, installer version and assets are updated together. Publication of source is separate from activation on 192.168.1.16. Its migration/startup acceptance remains unverified. Full SickChill parity is not claimed by this focused release.
