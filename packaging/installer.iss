; Inno Setup script — turns dist\Overshare into a normal Windows installer.
;
;   iscc packaging\installer.iss
;
; Produces dist\Overshare-Setup-<version>.exe: a wizard that installs per-user
; (so it never needs an admin prompt), adds a Start-menu entry, and optionally
; starts Overshare with Windows.

#define AppName "Overshare"
; CI passes the tag through as /DAppVersion=1.2.3; this is the local fallback.
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppPublisher "iota"
#define AppURL "https://github.com/iota-x/overshare"
#define AppExe "Overshare.exe"

[Setup]
AppId={{8F3A6C21-9E4D-4B77-A1E5-2C6D0B9F4A18}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; Per-user install: no UAC prompt, which keeps the first run friendly.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=Overshare-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
; Upgrading over a running copy: Inno shuts the app down itself and starts it
; again afterwards, so "update" doesn't mean "quit it first, then remember to
; open it again". AppMutex is what lets it detect the running instance.
CloseApplications=yes
RestartApplications=yes
AppMutex=Overshare.SingleInstance
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; \
  GroupDescription: "Shortcuts:"; Flags: unchecked
Name: "startupicon"; Description: "Start Overshare when I sign in"; \
  GroupDescription: "Startup:"

[Files]
; PyInstaller's COLLECT output — the exe plus everything it needs.
Source: "..\dist\Overshare\*"; DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: startupicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Open Overshare now"; \
  Flags: nowait postinstall skipifsilent

[UninstallDelete]
; The tray app writes here; leave the user's history alone unless they say so.
Type: dirifempty; Name: "{userappdata}\Overshare"

[Code]
// Offer to remove settings and history on uninstall, rather than assuming.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{userappdata}\Overshare');
    if DirExists(DataDir) then
      if MsgBox('Also delete your Overshare settings and activity history?' + #13#10 +
                'Choose No to keep them for a future reinstall.',
                mbConfirmation, MB_YESNO) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;
