; ============================================================
;  Inno Setup script — Dragon Ball Fusion World Tools
;
;  Prerequisites (developer machine only — not the end user):
;    1. Run build_windows.bat first to produce dist\DBFWTools.exe
;    2. Install Inno Setup 6 from https://jrsoftware.org/isinfo.php
;    3. Open this file in the Inno Setup IDE and click Compile,
;       OR run from the command line:
;         "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer_windows.iss
;
;  Output: installer_output\DBFWTools_Setup.exe
; ============================================================

[Setup]
AppName=Dragon Ball Fusion World Tools
AppVersion=1.0
AppPublisher=DBFW Tools
AppPublisherURL=https://github.com/ashkash13/dragon-ball-fusion-world
AppSupportURL=https://github.com/ashkash13/dragon-ball-fusion-world/issues
AppUpdatesURL=https://github.com/ashkash13/dragon-ball-fusion-world
DefaultDirName={autopf}\DBFWTools
DefaultGroupName=Dragon Ball Fusion World Tools
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=DBFWTools_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
; Require Windows 10 or later
MinVersion=10.0
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; \
  Description: "Create a &desktop shortcut"; \
  GroupDescription: "Additional shortcuts:"; \
  Flags: checked
Name: "startmenuicon"; \
  Description: "Create a Start &Menu shortcut"; \
  GroupDescription: "Additional shortcuts:"; \
  Flags: checked

[Files]
; The standalone binary produced by PyInstaller (build_windows.bat)
Source: "dist\DBFWTools.exe"; \
  DestDir: "{app}"; \
  Flags: ignoreversion

[Icons]
; Start Menu shortcut
Name: "{group}\Dragon Ball Fusion World Tools"; \
  Filename: "{app}\DBFWTools.exe"; \
  Tasks: startmenuicon
; Uninstall shortcut in Start Menu
Name: "{group}\Uninstall Dragon Ball Fusion World Tools"; \
  Filename: "{uninstallexe}"; \
  Tasks: startmenuicon
; Desktop shortcut
Name: "{autodesktop}\Dragon Ball Fusion World Tools"; \
  Filename: "{app}\DBFWTools.exe"; \
  Tasks: desktopicon

[Run]
; Offer to launch the app immediately after installation
Filename: "{app}\DBFWTools.exe"; \
  Description: "Launch Dragon Ball Fusion World Tools now"; \
  Flags: nowait postinstall skipifsilent

[Messages]
; Customise the welcome and finish page text
WelcomeLabel1=Welcome to Dragon Ball Fusion World Tools Setup
WelcomeLabel2=This wizard will install Dragon Ball Fusion World Tools on your computer.%n%nDBFW Tools scans your card photos to extract redemption codes and automatically enters them into the game — no manual typing required.%n%nClick Next to continue.
FinishedLabel=Dragon Ball Fusion World Tools has been installed successfully.%n%nOn first launch you will be prompted for a free Google Gemini API key, which is used to read codes from your card photos.
