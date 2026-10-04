# TV Manager v18.11.1 - Windows server updater

Added a standalone `update-server.ps1` for existing Windows source installations. It downloads a pinned GitHub release without requiring Git, preserves runtime data and configuration, makes a verified cold backup including the Python environment, installs dependencies and checks them before replacing source. Caught failures attempt source/environment rollback and return an error. The app remains stopped for an explicit restart and version check.

The updater rejects running installations, invalid archives, version mismatches, downgrades, unsafe/linked paths, bad database checks and insufficient backup space. It supports Windows PowerShell 5.1, installation paths containing spaces and deep backup paths. No production process, startup task, firewall or listening address is changed automatically.

[Download and run instructions](WINDOWS_SERVER_UPDATE.md) include a copy-and-paste command, backup location, recovery limits and Settings -> Network instructions for 192.168.1.11:5050. All v18.11.0 Network/readiness features are included.

Source: https://github.com/fpetillo/TV-Manager-Pro/tree/v18.11.1

ZIP: https://github.com/fpetillo/TV-Manager-Pro/archive/refs/tags/v18.11.1.zip

Script: https://raw.githubusercontent.com/fpetillo/TV-Manager-Pro/v18.11.1/update-server.ps1

Validation: 510 tests passed, two existing Windows symbolic-link privilege checks skipped. All 71 Python modules and 43 JavaScript assets parse; dependency consistency and PowerShell parsing pass. Twenty updater checks include actual Windows PowerShell 5.1 execution with a disposable Python environment, settings/data preservation, WAL backup recovery, invalid archive/path/version refusal, active-instance protection, low disk/damaged backup refusal and rollback after dependency/source failures. Details are recorded in RELEASE_MANIFEST.json. Tests use disposable databases/environments; they do not update the user's server. No executable/installer build or full SickChill parity certification is included.
