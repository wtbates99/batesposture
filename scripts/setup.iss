; BatesPosture — Inno Setup installer script
; Installs per-user with no administrator rights required.
; Build: ISCC /DAppVersion=1.0.0 /DOutputFilename=BatesPosture-v1.0.0-Setup scripts\setup.iss

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef OutputFilename
  #define OutputFilename "BatesPosture-Setup"
#endif

[Setup]
AppName=BatesPosture
AppVersion={#AppVersion}
AppPublisher=wtbates99
AppPublisherURL=https://github.com/wtbates99/batesposture
AppSupportURL=https://github.com/wtbates99/batesposture/issues
AppUpdatesURL=https://github.com/wtbates99/batesposture/releases

; Install to %LOCALAPPDATA%\Programs\BatesPosture (no UAC prompt)
DefaultDirName={autopf}\BatesPosture
DefaultGroupName=BatesPosture
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Output
OutputDir=..\installer-output
OutputBaseFilename={#OutputFilename}
SetupIconFile=..\src\static\icon.ico

; Compression
Compression=lzma2
SolidCompression=yes

; Appearance
WizardStyle=modern
DisableProgramGroupPage=yes
ShowLanguageDialog=no
UninstallDisplayIcon={app}\BatesPosture.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "startupicon"; Description: "Launch BatesPosture when &Windows starts"; GroupDescription: "Startup:"

[Files]
; Copy the entire PyInstaller onedir output into the install directory
Source: "..\dist\BatesPosture\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\BatesPosture"; Filename: "{app}\BatesPosture.exe"
Name: "{group}\Uninstall BatesPosture"; Filename: "{uninstallexe}"
Name: "{commondesktop}\BatesPosture"; Filename: "{app}\BatesPosture.exe"; Tasks: desktopicon
; Startup shortcut in user's Startup folder (no registry, no admin)
Name: "{userstartup}\BatesPosture"; Filename: "{app}\BatesPosture.exe"; Tasks: startupicon

[Run]
Filename: "{app}\BatesPosture.exe"; Description: "Launch BatesPosture now"; Flags: nowait postinstall skipifsilent
