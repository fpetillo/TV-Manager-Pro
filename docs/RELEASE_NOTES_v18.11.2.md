# TV Manager v18.11.2 â€” Optional browser login

Administrator login is now optional for both local and LAN access. Open **Settings -> Security** and leave **Require browser login (optional)** unchecked to use TV Manager without signing in. You can save a LAN listener or turn login off without first switching back to localhost. Turning login off takes effect immediately.

The update preserves existing enabled login settings and administrator credentials. If login is already enabled, sign in once, then uncheck the option. Enabling login still requires an administrator password, and authenticated writes retain CSRF checks. First-time password setup works over the LAN while login is off; existing passwords still require authentication to change. With login off, anyone able to reach the app can use it.

The Windows updater now defaults to **18.11.2**. Follow [server update instructions](WINDOWS_SERVER_UPDATE.md), then restart the installed application. The mandatory LAN-login instructions in the older v18.11.0 release notes are superseded by this release.

Also added a [Windows EXE/service assessment](WINDOWS_SERVICE_ASSESSMENT.md): existing packaging support, remaining service work and UNC network-library requirements. No service installer or new binary is delivered by this release.

Validation: 511 tests passed, two existing Windows symbolic-link privilege tests skipped. Python and changed JavaScript syntax passed. Real isolated routes verify login enable/disable, password login and CSRF; browser QA confirms Settings and Network over the LAN with no login. Production deployment remains separate.
