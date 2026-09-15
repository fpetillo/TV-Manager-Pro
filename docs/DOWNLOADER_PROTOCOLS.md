# Downloader protocols and acceptance scope

TV Manager v18.7.0 adds native uTorrent WebUI, rTorrent HTTP XML-RPC and Synology Download Station adapters alongside SABnzbd, NZBGet, qBittorrent, Transmission and Deluge Web. Configure methods under Settings → Download Clients → Choose Downloader Methods, then edit the corresponding connection.

## Protocol references

- [uTorrent WebUI API](https://github.com/bittorrent/webui/wiki/Web-UI-API): token/cookie session, file upload, label/pause operations and progress in thousandths.
- [rTorrent command reference](https://rtorrent-docs.readthedocs.io/en/latest/cmd-ref.html): HTTP XML-RPC, binary torrent load, separate label/path commands and queue snapshots. Configure the full HTTP XML-RPC URL. Direct SCGI sockets are not implemented.
- [Synology Download Station API](https://global.download.synology.com/download/Document/Software/DeveloperGuide/Package/DownloadStation/All/enu/Synology_Download_Station_Web_API.pdf): discovery, authenticated sessions, task creation/listing and logout. The adapter discovers CGI locations and supported versions, using SYNO.DownloadStation.Task. Configure the DSM address and a path relative to a shared folder.
- [SickChill processing implementation](https://github.com/SickChill/sickchill/blob/master/sickchill/oldbeard/postProcessor.py): processing method semantics and six appended script arguments were checked against upstream. No upstream implementation was copied into TV Manager.
- [rarfile API](https://rarfile.readthedocs.io/api.html): RAR enumeration/extraction through a compatible extractor. Windows bsdtar argument ordering is adapted locally for rarfile 4.5.

## Identity and restart behavior

HTTP torrent descriptors are validated and their original info dictionary is hashed. qBittorrent and the new torrent clients use this identity instead of guessing a queue item by title. Deluge distinguishes magnet and file submission. Watch folders receive actual NZB/torrent contents; magnets need a direct client.

Before handoff, TV Manager records an intent and reserves affected episodes in SQLite. Season-pack reservations cover the whole season to prevent overlap with individual submissions. A receipt is committed before local acquisition finalization. Timeouts or failed local writes retain the reservation; the release is not automatically resent. Download Center lets an operator record an accepted client ID or confirm absence from the client queue/history. A lock prevents resolving a request while it is still sending.

This is not an exactly-once guarantee across remote services. Restoring a database, incorrectly clearing a hold, or losing client history can require reconciliation. Restoration pauses automation for that reason.

## Verified and unverified coverage

Fixtures test token authentication, binary identity, XML-RPC serialization, Synology discovery/login/task identity/logout, progress/status mapping and rejected configuration. Browser checks verify handoff review and typed settings. No real release was submitted to an external downloader during testing.

Live compatibility requires configured clients. Deluge daemon, MLDonkey and put.io remain absent. Seeding ratio/time, priority and destination options are not fully equivalent across all clients. Site-specific provider login/scraping is separate. Password-protected archives are unsupported.
