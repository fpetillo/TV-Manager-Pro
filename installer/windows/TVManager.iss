; TV Manager Inno Setup starter script
#define MyAppName "TV Manager"
#define MyAppVersion "17.14.0"
#define MyAppPublisher "Acuityware"
#define MyAppExeName "TVManager.exe"

[Setup]
AppId={{4A8A1977-ACUITYWARE-TVMANAGER}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\TV Manager
DefaultGroupName=TV Manager
DisableProgramGroupPage=yes
OutputBaseFilename=TVManagerSetup-17.14.0
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\..\release\windows\TVManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "tvmanager.db,.env,logs\*,diagnostics\*,backups\*,managed_trash\*"

[Icons]
Name: "{group}\TV Manager"; Filename: "{app}\run.ps1"; WorkingDir: "{app}"
Name: "{group}\TV Manager Launchpad"; Filename: "http://127.0.0.1:5050/launchpad"

[Run]
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File \"{app}\setup.ps1\""; WorkingDir: "{app}"; Flags: postinstall runhidden
