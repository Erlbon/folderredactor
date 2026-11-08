#if 0
; The Windows installer of The Ⅎolder Redactor (Inno Setup 6): the one-folder build (dist\folderredactor\, built with
; FOLDERREDACTOR_BUILD=folder; it starts faster than the one-file exe, which unpacks itself at every start) into the
; user's own programs folder, with a Start menu entry. The one-file dist\folderredactor.exe stays the portable download.
;
; Build:   build_exe.bat (it builds both programs and passes /DUpdateContract), or by hand:
;          iscc /DAppBuild=2026-11-08#03 /DUpdateContract=<python -m redactor_common.release contract-path> installer\folderredactor.iss
; Output:  dist\folderredactor-setup.exe
;
; Per user, no administrator rights: %LOCALAPPDATA%\Programs\The Folder Redactor. Updating goes through the family's
; update framework (redactor_common docs/update-framework.md): its installer contract, included at the END of this
; file, writes {app}\update-channel = windows-installer, so Help > Check for Updates runs the new
; folderredactor-setup.exe the release's update-manifest.json names, silently with /relaunch=yes, and the contract
; starts the program again. The settings, crash log and History sit beside the exe (the Redactor apps' convention):
; an update leaves them, and so does the uninstall.
;
; These notes sit in "#if 0", as in the shared contract.
#endif

#ifndef AppBuild
  #define AppBuild "0000-00-00#00"
#endif
#ifndef UpdateContract
  #error Pass /DUpdateContract (build_exe.bat does: python -m redactor_common.release contract-path)
#endif

; For the installer contract included at the end. The program has no --quit: Windows' close request ends it.
#define UpdateExe "folderredactor.exe"

[Setup]
AppId={{EC5101A1-10C3-479D-9069-EF4B1DFF1A29}
AppName=The Ⅎolder Redactor
AppVersion={#AppBuild}
AppVerName=The Ⅎolder Redactor {#AppBuild}
AppPublisher=Erlbon
AppPublisherURL=https://github.com/Erlbon/folderredactor
AppSupportURL=https://github.com/Erlbon/folderredactor/issues
AppUpdatesURL=https://github.com/Erlbon/folderredactor/releases
VersionInfoVersion=0.0.0.0
VersionInfoProductTextVersion={#AppBuild}
PrivilegesRequired=lowest
DefaultDirName={autopf}\The Folder Redactor
DefaultGroupName=The Ⅎolder Redactor
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\folderredactor.exe
UninstallDisplayName=The Ⅎolder Redactor
SetupIconFile=..\assets\icon.ico
LicenseFile=..\LICENSE
OutputDir=..\dist
OutputBaseFilename=folderredactor-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "A shortcut on the desktop"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\folderredactor\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\The Ⅎolder Redactor"; Filename: "{app}\folderredactor.exe"
Name: "{autodesktop}\The Ⅎolder Redactor"; Filename: "{app}\folderredactor.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\folderredactor.exe"; Description: "Start The Ⅎolder Redactor"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; what Help > Check for Updates may leave beside the exe: the old exe after a swap, and a download that did not finish
Type: files; Name: "{app}\folderredactor.exe.old"
Type: files; Name: "{app}\folderredactor.exe.new"
Type: files; Name: "{app}\folderredactor.exe.new.part"

#include UpdateContract
