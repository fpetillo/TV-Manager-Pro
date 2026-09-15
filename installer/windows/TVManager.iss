; TV Manager Inno Setup starter script
#define MyAppName "TV Manager"
#define MyAppVersion "18.7.0"
#define MyAppPublisher "Acuityware"
#define MyAppExeName "TVManager.exe"

[Setup]
AppId={{4A8A1977-ACUITYWARE-TVMANAGER}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\TV Manager
PrivilegesRequired=lowest
DefaultGroupName=TV Manager
DisableProgramGroupPage=yes
OutputBaseFilename=TVManagerSetup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\..\release\windows\TVManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.db,*.db-wal,*.db-shm,.env,*.ini,.tvmanager-session-key,logs\*,diagnostics\*,backups\*,managed_trash\*,recovery\*,archive-staging\*,.runtime\*,.acquisition-locks\*,rename-journals\*"

[Icons]
Name: "{group}\TV Manager"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\TV Manager Launchpad"; Filename: "http://127.0.0.1:5050/launchpad"

[Run]
Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Flags: postinstall nowait skipifsilent
