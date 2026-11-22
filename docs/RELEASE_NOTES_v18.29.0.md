# TV Manager v18.29.0 — TV shows and movies, one view

Built on v18.28.0.

## What changed

Movies are now part of the whole app, not a separate page bolted on.

- **Dashboard** — two matching cards side by side, **TV Shows** and **Movies**, each with its live state (automation on, needs setup, next movie release) and six counts that open the right page. A **Recently added** poster rail mixes newly imported episodes and movies. **Downloads** is one feed for both, with an All / TV / Movies switch. **Recent Activity** marks each event TV, Movie or System. **Automation** groups jobs under TV, Movies and System with readable names and intervals. **System Health** shows whether movie automation is ready.
- **Insights** — movie setup problems, failed movie downloads, wanted movies and movies added this week appear with the TV insights, most urgent first.
- **Search** (the ⌘ / palette on every page) finds movies by title, IMDb or TMDb ID and opens the movie page.
- **Movie page** (`/movie/<id>`) — poster and backdrop, rating, genres, quality, status, overview; Search and download / Look for an upgrade, Ignore or Want, TMDb and IMDb links; every release from the last search with the reason any was rejected; download history with Try another release; the movie's activity. Library cards on Movies open it.
- **Upcoming** — renamed from Upcoming Episodes. Wanted movies arriving on digital or disc are listed under the episodes and shown in the calendar (🎬). The private calendar subscription (`calendar.ics`) includes them too.
- **Queue** — a Movie downloads section shows movies in progress and recently finished.
- **Launchpad** — Movies and Movies wanted counts, and movie setup problems among the recommended actions.
- **Navigation** — Library is now "TV shows & movies", with Movies directly under Shows. Movie pages highlight Movies in the menu.
- **Notifications** — Discord, Slack, Pushover and the other services name the movie ("Movie snatched: …", "Movie added to Plex: …").
- **Browser icon** redrawn in the TV Manager Pro brand (slate TV, orange antenna, blue swoosh, red play) to match the logo.

All new components follow the four themes (Classic, Glassy, Midnight, Daylight).

## Updating to 18.29.0

Download `update-server.ps1` from the v18.29.0 tag and run it, as in [WINDOWS_SERVER_UPDATE.md](WINDOWS_SERVER_UPDATE.md); start TV Manager with run.ps1; press Ctrl+F5 in the browser.

## Validation

- 6 new tests: movie dashboard counts (wanted vs coming to digital, imported and failed this week, recent excludes Plex-found movies), setup problems in the dashboard and insights, movie calendar, search and detail (events filtered to the movie), movie notification text, templates and menu order, and the running app (dashboard, search, insights, launchpad, calendar API, calendar.ics, movie detail and six pages).
- Chrome on a disposable copy with sample shows, episodes, movies and downloads: dashboard, movie page, Upcoming, Queue, Launchpad and Movies at desktop and phone width, Classic and Daylight themes; no page errors or server errors.
