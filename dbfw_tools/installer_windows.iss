; ============================================================
;  Inno Setup 6 script — Dragon Ball Fusion World Tools
;
;  Installer flow:
;    1. Welcome screen
;    2. Dependencies overview — lists everything that will be
;       installed and shows whether Python is already present
;    3. Destination folder selection
;    4. Optional shortcut selection
;    5. Ready to Install
;    6. Installing:
;         a. Python downloaded + installed if not found
;            (user is asked to confirm before any download)
;         b. App source files copied
;         c. Isolated Python virtual environment created
;         d. Python packages installed into the venv
;         e. No-console VBScript launcher created
;    7. Installation summary — exact paths of everything installed
;    8. Finish / launch option
;
;  Uninstaller flow:
;    1. Confirmation dialog listing everything that will be removed
;    2. Removes: venv, config files, app files, shortcuts, registry
;    3. Summary dialog confirming what was removed
;
;  Prerequisites (developer machine only):
;    - Inno Setup 6: https://jrsoftware.org/isinfo.php
;    - The dbfw_tools\ source folder
;
;  To build:
;    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer_windows.iss
;  Output: installer_output\DBFWTools_Setup.exe
; ============================================================

[Setup]
AppName=Dragon Ball Fusion World Tools
AppVersion=1.0
AppPublisher=DBFW Tools
AppPublisherURL=https://github.com/ashkash13/dragon-ball-fusion-world
AppSupportURL=https://github.com/ashkash13/dragon-ball-fusion-world/issues
DefaultDirName={autopf}\DBFWTools
DefaultGroupName=Dragon Ball Fusion World Tools
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=DBFWTools_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
MinVersion=10.0
; Allow installing as current user (no admin required) or as admin
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayName=Dragon Ball Fusion World Tools

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "startmenuicon"; Description: "Create a Start &Menu shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
; Application source files
Source: "main.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "src\*"; DestDir: "{app}\src"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "__pycache__,*.pyc,*.pyo"

[Icons]
; Shortcuts point to the no-console VBScript launcher created post-install
Name: "{group}\Dragon Ball Fusion World Tools"; Filename: "{app}\launch.vbs"; Tasks: startmenuicon
Name: "{group}\Uninstall Dragon Ball Fusion World Tools"; Filename: "{uninstallexe}"; Tasks: startmenuicon
Name: "{autodesktop}\Dragon Ball Fusion World Tools"; Filename: "{app}\launch.vbs"; Tasks: desktopicon

[Run]
; Step 1: Create an isolated Python virtual environment in the install folder.
;         This keeps all packages for this app separate from the rest of the system.
Filename: "{code:GetPythonExe}"; Parameters: "-m venv ""{app}\.venv"""; StatusMsg: "Step 1 of 2  —  Creating isolated Python environment in {app}\.venv ..."; Flags: runhidden waituntilterminated

; Step 2: Install the required Python packages into the venv.
;         Packages: google-genai, Pillow, tkinterdnd2, pyautogui, pygetwindow, requests
;         Flags: no runhidden — a console window shows live pip progress so users can see it working.
Filename: "{app}\.venv\Scripts\pip.exe"; Parameters: "install -r ""{app}\requirements.txt"""; StatusMsg: "Step 2 of 2  —  Downloading and installing packages (google-genai, Pillow, pyautogui ...).  A progress window shows download activity.  This takes 1-3 minutes."; Flags: waituntilterminated

; Offer to launch immediately after installation
Filename: "{app}\launch.vbs"; Description: "Launch Dragon Ball Fusion World Tools now"; Flags: nowait postinstall skipifsilent shellexec

[Code]

// ── Global state ──────────────────────────────────────────────────────────────

var
  { Install-time Python state }
  PythonExePath:          string;   // full path to python.exe
  InstalledPythonVersion: string;   // e.g. "3.14.0"
  PythonInstalledByUs:    Boolean;  // True if we downloaded + installed it

  { Custom wizard pages }
  DepsPage:    TOutputMsgWizardPage;
  SummaryPage: TOutputMsgWizardPage;

  { Uninstall-time state — captured before any files are removed }
  UninstallAppDir:       string;
  UninstallVenvDir:      string;
  UninstallConfigDir:    string;
  UninstallVenvExisted:  Boolean;
  UninstallCfgExisted:   Boolean;
  UninstallVenvRemoved:  Boolean;
  UninstallCfgRemoved:   Boolean;
  KeepCfg:               Boolean;  // True = user chose to keep API key on uninstall

// ── Utility ───────────────────────────────────────────────────────────────────

procedure RemoveDirRecursive(Path: string);
{ Deletes a directory and all its contents using cmd.exe rmdir /S /Q. }
var
  ResultCode: Integer;
begin
  if DirExists(Path) then
    Exec(ExpandConstant('{sys}\cmd.exe'),
      '/C rmdir /S /Q "' + Path + '"',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

// ── Python detection ──────────────────────────────────────────────────────────

function ExtractLeadingInt(S: string; Default: Integer): Integer;
{ Returns the integer value of the leading digit characters in S.
  Stops at the first non-digit. Returns Default if no digits are found.
  Example: "14-32" → 14,  "11" → 11,  "foo" → Default. }
var
  NumStr: string;
  I: Integer;
begin
  NumStr := '';
  for I := 1 to Length(S) do
  begin
    if (S[I] >= '0') and (S[I] <= '9') then
      NumStr := NumStr + S[I]
    else
      Break;
  end;
  if NumStr = '' then
    Result := Default
  else
    Result := StrToIntDef(NumStr, Default);
end;

function FindPythonInRegistry(): string;
{ Dynamically enumerates ALL Python versions installed on this machine
  (both per-user HKCU and system-wide HKLM) and returns the path to
  python.exe for the highest version that is >= 3.11.

  Works for any future Python release without requiring installer updates:
  3.15, 3.16, 3.20, etc. are all discovered automatically.

  Handles 32-bit variants (e.g. key "3.14-32") and skips pre-release keys
  that cannot be parsed as a plain minor version number. }
var
  Hives:       array[0..1] of Integer;
  Subkeys:     TArrayOfString;
  J, I:        Integer;
  DotPos:      Integer;
  VerStr:      string;
  InstallPath, ExePath: string;
  CurMinor, BestMinor:  Integer;
begin
  Result    := '';
  BestMinor := 10;   // anything found must be > 3.10 (i.e. 3.11+)

  Hives[0] := HKCU;
  Hives[1] := HKLM;

  for J := 0 to 1 do
  begin
    if not RegGetSubkeyNames(Hives[J], 'SOFTWARE\Python\PythonCore', Subkeys) then
      Continue;

    for I := 0 to GetArrayLength(Subkeys) - 1 do
    begin
      VerStr := Subkeys[I];   // e.g. "3.14"  or  "3.14-32"

      // Must start with "3."
      DotPos := Pos('.', VerStr);
      if (DotPos < 2) or (Copy(VerStr, 1, DotPos - 1) <> '3') then
        Continue;

      // Extract minor version from the text after the dot ("14" from "3.14-32")
      CurMinor := ExtractLeadingInt(Copy(VerStr, DotPos + 1, Length(VerStr)), -1);
      if CurMinor <= BestMinor then
        Continue;   // not newer than what we already have (or below 3.11)

      // Verify python.exe actually exists at this registry entry
      InstallPath := '';
      if not (RegQueryStringValue(Hives[J],
                'SOFTWARE\Python\PythonCore\' + VerStr + '\InstallPath',
                '', InstallPath)) then
        Continue;
      if (Length(InstallPath) > 0) and (InstallPath[Length(InstallPath)] <> '\') then
        InstallPath := InstallPath + '\';
      ExePath := InstallPath + 'python.exe';
      if not FileExists(ExePath) then
        Continue;

      // New best match
      BestMinor := CurMinor;
      Result    := ExePath;
    end;
  end;
end;

function GetPythonVersionString(PythonExe: string): string;
{ Runs "python --version" and returns just the version number, e.g. "3.14.0". }
var
  TempFile: string;
  Lines: TArrayOfString;
  ResultCode: Integer;
  Ver: string;
begin
  Result := '';
  if PythonExe = '' then Exit;
  TempFile := ExpandConstant('{tmp}\pyver.txt');
  Exec(ExpandConstant('{sys}\cmd.exe'),
    '/C ""' + PythonExe + '" --version > "' + TempFile + '" 2>&1"',
    '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if LoadStringsFromFile(TempFile, Lines) and (GetArrayLength(Lines) > 0) then
  begin
    Ver := Trim(Lines[0]);
    // "Python 3.14.0" → "3.14.0"
    if Copy(Ver, 1, 7) = 'Python ' then
      Result := Copy(Ver, 8, Length(Ver));
  end;
end;

{ Called by [Run] entries via {code:GetPythonExe} }
function GetPythonExe(Param: string): string;
begin
  Result := PythonExePath;
end;

// ── Dependencies page text ────────────────────────────────────────────────────

function BuildDepsPageText(): string;
var
  PythonBlock: string;
  HomeDir: string;
begin
  HomeDir := ExpandConstant('{%USERPROFILE}');

  if PythonExePath <> '' then
    PythonBlock :=
      '  Status   Already installed  (Python ' + InstalledPythonVersion + ')' + #13#10 +
      '  Location ' + PythonExePath + #13#10 +
      '  No download is needed.'
  else
    PythonBlock :=
      '  Status   Not found on this computer.' + #13#10 +
      '  Action   You will be asked to confirm before anything is downloaded.' + #13#10 +
      '           The latest stable Python (~25 MB) will then be fetched' + #13#10 +
      '           from python.org and installed automatically.';

  Result :=
    'WHAT THIS INSTALLER WILL SET UP' + #13#10 +
    '================================================================' + #13#10 +
    #13#10 +
    'PYTHON  (required runtime)' + #13#10 +
    '----------------------------------------------------------------' + #13#10 +
    PythonBlock + #13#10 +
    #13#10 +
    'PYTHON PACKAGES  (installed into an isolated environment)' + #13#10 +
    '----------------------------------------------------------------' + #13#10 +
    '  These packages are installed inside a private .venv folder' + #13#10 +
    '  in the app directory. They are completely isolated and will' + #13#10 +
    '  NOT affect any other Python programs on your computer.' + #13#10 +
    #13#10 +
    '  google-genai    AI image analysis via Google Gemini' + #13#10 +
    '  Pillow          image file reading and processing' + #13#10 +
    '  tkinterdnd2     drag-and-drop file support' + #13#10 +
    '  pyautogui       keyboard / mouse automation  (Redeemer tab)' + #13#10 +
    '  pygetwindow     game window detection' + #13#10 +
    '  requests        Discord API communication' + #13#10 +
    #13#10 +
    'APP FILES' + #13#10 +
    '----------------------------------------------------------------' + #13#10 +
    '  Source code, the .venv folder, and the app launcher will be' + #13#10 +
    '  installed to the folder you choose on the next screen.' + #13#10 +
    #13#10 +
    'DISK SPACE REQUIRED' + #13#10 +
    '----------------------------------------------------------------' + #13#10 +
    '  Python packages (downloaded during install)   ~250 MB' + #13#10 +
    '  Application source code                         ~1 MB' + #13#10 +
    '  Python itself (only if not already installed)  ~80 MB' + #13#10 +
    '  Total estimate: ~270 MB (Python present) or ~350 MB (new install)' + #13#10 +
    #13#10 +
    'CONFIGURATION  (written automatically on first launch)' + #13#10 +
    '----------------------------------------------------------------' + #13#10 +
    '  ' + HomeDir + '\.dbfw_tools\' + #13#10 +
    '    config.json    Gemini API key and Discord settings' + #13#10 +
    '    scanner.log    Scanner activity log  (max 1 MB, rotating)' + #13#10 +
    '    redeemer.log   Redeemer activity log  (max 1 MB, rotating)' + #13#10 +
    #13#10 +
    '================================================================' + #13#10 +
    'Click Next to continue.  Click Cancel at any time to abort.';
end;

// ── Installation summary page text ────────────────────────────────────────────

function BuildSummaryPageText(): string;
var
  AppDir, HomeDir: string;
  PythonLine, ShortcutLines: string;
begin
  AppDir  := ExpandConstant('{app}');
  HomeDir := ExpandConstant('{%USERPROFILE}');

  if PythonInstalledByUs then
    PythonLine :=
      '  Installed by this wizard   Python ' + InstalledPythonVersion + #13#10 +
      '  Location: ' + PythonExePath
  else
    PythonLine :=
      '  Was already present   Python ' + InstalledPythonVersion + #13#10 +
      '  Location: ' + PythonExePath;

  ShortcutLines := '';
  if IsTaskSelected('desktopicon') then
    ShortcutLines := ShortcutLines + '  Desktop shortcut     Created' + #13#10;
  if IsTaskSelected('startmenuicon') then
    ShortcutLines := ShortcutLines + '  Start Menu shortcut  Created' + #13#10;
  if ShortcutLines = '' then
    ShortcutLines := '  No shortcuts were created.' + #13#10;

  Result :=
    'INSTALLATION SUMMARY' + #13#10 +
    '================================================================' + #13#10 +
    #13#10 +
    'PYTHON' + #13#10 +
    '----------------------------------------------------------------' + #13#10 +
    PythonLine + #13#10 +
    #13#10 +
    'APPLICATION FILES' + #13#10 +
    '----------------------------------------------------------------' + #13#10 +
    '  ' + AppDir + '\' + #13#10 +
    '    main.py           app entry point' + #13#10 +
    '    requirements.txt  package list' + #13#10 +
    '    src\              application source code' + #13#10 +
    #13#10 +
    'PYTHON VIRTUAL ENVIRONMENT' + #13#10 +
    '----------------------------------------------------------------' + #13#10 +
    '  ' + AppDir + '\.venv\' + #13#10 +
    '  Packages: google-genai, Pillow, tkinterdnd2, pyautogui,' + #13#10 +
    '            pygetwindow, requests' + #13#10 +
    #13#10 +
    'APP LAUNCHER  (runs the app with no console window)' + #13#10 +
    '----------------------------------------------------------------' + #13#10 +
    '  ' + AppDir + '\launch.vbs' + #13#10 +
    #13#10 +
    'SHORTCUTS' + #13#10 +
    '----------------------------------------------------------------' + #13#10 +
    ShortcutLines +
    #13#10 +
    'CONFIGURATION  (created on first launch)' + #13#10 +
    '----------------------------------------------------------------' + #13#10 +
    '  ' + HomeDir + '\.dbfw_tools\' + #13#10 +
    '    config.json    stores your Gemini API key + Discord settings' + #13#10 +
    '    scanner.log    Scanner activity log' + #13#10 +
    '    redeemer.log   Redeemer activity log' + #13#10 +
    #13#10 +
    '================================================================' + #13#10 +
    'TO UNINSTALL:' + #13#10 +
    '  Settings -> Apps -> Dragon Ball Fusion World Tools -> Uninstall' + #13#10 +
    '  The uninstaller will show you exactly what will be removed' + #13#10 +
    '  and ask for confirmation before deleting anything.';
end;

// ── Wizard initialisation — runs before the first page is shown ───────────────

procedure InitializeWizard;
begin
  { Detect Python now so the Dependencies page can show its current status. }
  PythonExePath := FindPythonInRegistry();
  if PythonExePath <> '' then
    InstalledPythonVersion := GetPythonVersionString(PythonExePath);

  { Page A (inserted after Welcome): dependency overview }
  DepsPage := CreateOutputMsgPage(wpWelcome,
    'Dependencies and What Will Be Installed',
    'Please review before continuing',
    BuildDepsPageText());

  { Page B (inserted after the install step): installation summary }
  SummaryPage := CreateOutputMsgPage(wpInstalling,
    'Installation Summary',
    'A complete record of what was installed and where',
    'Installation in progress — this page will fill in automatically...');
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  { Fill in exact paths once the user navigates to the summary page.
    By this point ssPostInstall has already run and {app} is known. }
  if CurPageID = SummaryPage.ID then
    SummaryPage.RichEditViewer.Lines.Text := BuildSummaryPageText();
end;

// ── Python download and silent install ────────────────────────────────────────

function DownloadAndInstallPython(): Boolean;
var
  TempFile, VersionFile, LatestVersion: string;
  ResultCode: Integer;
  PSExe, PSArgs: string;
  Lines: TArrayOfString;
begin
  Result := False;
  TempFile    := ExpandConstant('{tmp}\python_installer.exe');
  VersionFile := ExpandConstant('{tmp}\py_version.txt');
  PSExe       := ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe');

  // ── Step 1: Query python.org to find the latest stable release ────────────
  // Parses the FTP directory listing; only pure numeric "3.x.y" entries match
  // (pre-releases like "3.14.0a1" are automatically excluded by the regex).
  WizardForm.PreparingLabel.Caption :=
    'Checking python.org for the latest stable Python release...';
  WizardForm.Update;

  PSArgs :=
    '-NoProfile -NonInteractive -Command ' +
    '"[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; ' +
    '$mlist=[regex]::Matches(' +
      '(Invoke-WebRequest ''https://www.python.org/ftp/python/'' -UseBasicParsing).Content,' +
      '''>(3\.\d+\.\d+)/<''); ' +
    '$v=($mlist | ForEach-Object {[version]$_.Groups[1].Value} | ' +
    'Where-Object {$_.Minor -ge 11} | Sort-Object -Descending | ' +
    'Select-Object -First 1).ToString(); ' +
    'Set-Content -Path ''' + VersionFile + ''' -Value $v"';

  LatestVersion := '3.14.0';  // fallback if the FTP query fails
  if Exec(PSExe, PSArgs, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and
     (ResultCode = 0) and
     LoadStringsFromFile(VersionFile, Lines) and
     (GetArrayLength(Lines) > 0) then
  begin
    LatestVersion := Trim(Lines[0]);
    if (Length(LatestVersion) < 5) or (LatestVersion[1] <> '3') then
      LatestVersion := '3.14.0';
  end;

  // ── Step 2: Download the Python installer ─────────────────────────────────
  WizardForm.PreparingLabel.Caption :=
    'Downloading Python ' + LatestVersion + ' from python.org  (~25 MB)  Please wait...';
  WizardForm.Update;

  PSArgs :=
    '-NoProfile -NonInteractive -Command ' +
    '"[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; ' +
    'Invoke-WebRequest ' +
    '-Uri ''https://www.python.org/ftp/python/' + LatestVersion + '/python-' + LatestVersion + '-amd64.exe'' ' +
    '-OutFile ''' + TempFile + ''' ' +
    '-UseBasicParsing"';

  if not Exec(PSExe, PSArgs, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or
     (ResultCode <> 0) then
  begin
    MsgBox(
      'Could not download Python ' + LatestVersion + '.' + #13#10 +
      'Please check your internet connection and try again.' + #13#10 + #13#10 +
      'You can also install Python manually from:' + #13#10 +
      'https://www.python.org/downloads/' + #13#10 + #13#10 +
      'Make sure to check "Add Python to PATH" during installation,' + #13#10 +
      'then run this installer again.',
      mbError, MB_OK);
    Exit;
  end;

  // ── Step 3: Run the Python installer ──────────────────────────────────────
  // /passive        shows a minimal progress bar, no interaction required
  // InstallAllUsers=0  installs for the current user only (no admin needed)
  // PrependPath=1      adds Python to PATH
  // Include_tcltk=1    includes tkinter (required by this app)
  // Include_pip=1      includes pip
  WizardForm.PreparingLabel.Caption :=
    'Installing Python ' + LatestVersion + '  (a small progress window will appear)...';
  WizardForm.Update;

  if not Exec(TempFile,
    '/passive InstallAllUsers=0 PrependPath=1 Include_tcltk=1 Include_pip=1',
    '', SW_SHOW, ewWaitUntilTerminated, ResultCode) or (ResultCode <> 0) then
  begin
    MsgBox(
      'The Python installer did not complete successfully.' + #13#10 + #13#10 +
      'Please install Python 3.11 or newer manually from:' + #13#10 +
      'https://www.python.org/downloads/' + #13#10 + #13#10 +
      'Check "Add Python to PATH" during installation, then run this installer again.',
      mbError, MB_OK);
    Exit;
  end;

  // ── Step 4: Locate the newly installed Python ──────────────────────────────
  PythonExePath := FindPythonInRegistry();
  if PythonExePath <> '' then
  begin
    InstalledPythonVersion := GetPythonVersionString(PythonExePath);
    PythonInstalledByUs    := True;
  end;

  Result := PythonExePath <> '';

  if not Result then
    MsgBox(
      'Python was installed but could not be located in the registry.' + #13#10 +
      'Please restart your computer and run this installer again.',
      mbError, MB_OK);
end;

// ── PrepareToInstall — runs when the user clicks Install ──────────────────────

function PrepareToInstall(var NeedsRestart: Boolean): string;
begin
  Result := '';
  NeedsRestart := False;

  // Python was already found in InitializeWizard — nothing to do.
  if PythonExePath <> '' then Exit;

  // Last-chance registry check (e.g. user installed Python after launching wizard).
  PythonExePath := FindPythonInRegistry();
  if PythonExePath <> '' then
  begin
    InstalledPythonVersion := GetPythonVersionString(PythonExePath);
    Exit;
  end;

  // Python is missing. Ask the user before downloading anything.
  if MsgBox(
    'Python 3.11 or newer is required but was not found on this computer.' + #13#10 + #13#10 +
    'This installer can download and install the latest Python for you.' + #13#10 +
    'The download is approximately 25 MB from python.org.' + #13#10 + #13#10 +
    'Click Yes to download and install Python automatically.' + #13#10 +
    'Click No to cancel — you can install Python yourself from python.org.',
    mbConfirmation, MB_YESNO) = IDNO then
  begin
    Result := 'Python is required. Install Python 3.11 or newer from ' +
              'https://www.python.org/downloads/ ' +
              '(check "Add Python to PATH"), then run this installer again.';
    Exit;
  end;

  if not DownloadAndInstallPython() then
    Result := 'Python could not be installed automatically. ' +
              'Please install Python 3.11+ from python.org and run this installer again.';
end;

// ── Post-install: create the no-console VBScript launcher ────────────────────

procedure CurStepChanged(CurStep: TSetupStep);
var
  ScriptPath: string;
  Lines: TArrayOfString;
  I: Integer;
begin
  if CurStep <> ssPostInstall then Exit;

  // launch.vbs uses pythonw.exe so the app opens without a console window.
  ScriptPath := ExpandConstant('{app}\launch.vbs');
  SetArrayLength(Lines, 5);
  Lines[0] := 'Set oShell = CreateObject("WScript.Shell")';
  Lines[1] := 'AppDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))';
  Lines[2] := 'If Right(AppDir, 1) <> "\" Then AppDir = AppDir & "\"';
  Lines[3] := 'oShell.CurrentDirectory = AppDir';
  Lines[4] := 'oShell.Run Chr(34) & AppDir & ".venv\Scripts\pythonw.exe" & Chr(34) & " main.py", 0, False';

  if not SaveStringToFile(ScriptPath, '', False) then Exit;
  for I := 0 to GetArrayLength(Lines) - 1 do
    SaveStringToFile(ScriptPath, Lines[I] + #13#10, True);
end;

// ── Uninstaller ───────────────────────────────────────────────────────────────

function InitializeUninstall(): Boolean;
{ Called before the uninstall progress form appears.
  Shows exactly what will be removed and asks for confirmation.
  Returns False to cancel the uninstall. }
var
  Msg: string;
begin
  // Capture paths now, before the uninstaller removes anything.
  UninstallAppDir    := ExpandConstant('{app}');
  UninstallVenvDir   := UninstallAppDir + '\.venv';
  UninstallConfigDir := ExpandConstant('{%USERPROFILE}') + '\.dbfw_tools';

  UninstallVenvExisted := DirExists(UninstallVenvDir);
  UninstallCfgExisted  := DirExists(UninstallConfigDir);

  Msg :=
    'UNINSTALL — Dragon Ball Fusion World Tools' + #13#10 +
    '================================================================' + #13#10 +
    #13#10 +
    'The following will be permanently removed from your computer:' + #13#10 +
    #13#10 +
    '  Application files' + #13#10 +
    '    ' + UninstallAppDir + '\' + #13#10 +
    '    (source code and app launcher)' + #13#10 +
    #13#10;

  if UninstallVenvExisted then
    Msg := Msg +
      '  Python virtual environment  (all installed packages)' + #13#10 +
      '    ' + UninstallVenvDir + '\' + #13#10 +
      '    Note: this folder may be several hundred MB.' + #13#10 +
      #13#10;

  if UninstallCfgExisted then
    Msg := Msg +
      '  Configuration and log files  (you will be asked separately)' + #13#10 +
      '    ' + UninstallConfigDir + '\' + #13#10 +
      '    (Gemini API key, Discord settings, log files)' + #13#10 +
      #13#10;

  Msg := Msg +
    '  Desktop and Start Menu shortcuts  (if they were created)' + #13#10 +
    '  Add/Remove Programs entry' + #13#10 +
    #13#10 +
    '----------------------------------------------------------------' + #13#10 +
    'Python itself will NOT be removed.' + #13#10 +
    'To uninstall Python: Settings -> Apps -> search "Python"' + #13#10 +
    '================================================================' + #13#10 +
    #13#10 +
    'Click Yes to begin the uninstall process.' + #13#10 +
    'Click No to cancel and keep the application.' + #13#10 +
    #13#10 +
    '(You will be asked about your saved settings on the next screen.)';

  // Default button is No — the user must actively choose Yes.
  Result := (MsgBox(Msg, mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES);
  if not Result then Exit;

  // If config folder exists, ask separately — user may want to keep API key.
  KeepCfg := False;
  if UninstallCfgExisted then
  begin
    KeepCfg := (MsgBox(
      'Your saved settings are stored at:' + #13#10 +
      '  ' + UninstallConfigDir + #13#10 +
      #13#10 +
      'This folder contains your Gemini API key and Discord settings.' + #13#10 +
      #13#10 +
      'Delete these settings?' + #13#10 +
      '  Yes = remove everything  (full clean uninstall)' + #13#10 +
      '  No  = keep your API key  (useful if you plan to reinstall)',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDNO);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  SummaryMsg: string;
begin
  case CurUninstallStep of

    usUninstall:
    begin
      // Remove the virtual environment.
      // The standard uninstaller only tracks files in [Files]; the .venv was
      // created by a [Run] command and must be deleted explicitly.
      if UninstallVenvExisted then
      begin
        RemoveDirRecursive(UninstallVenvDir);
        UninstallVenvRemoved := not DirExists(UninstallVenvDir);
      end;

      // Remove configuration and log files — only if user did not choose to keep them.
      if UninstallCfgExisted and not KeepCfg then
      begin
        RemoveDirRecursive(UninstallConfigDir);
        UninstallCfgRemoved := not DirExists(UninstallConfigDir);
      end;
    end;

    usPostUninstall:
    begin
      SummaryMsg :=
        'UNINSTALL COMPLETE' + #13#10 +
        '================================================================' + #13#10 +
        #13#10 +
        'The following have been removed from your computer:' + #13#10 +
        #13#10 +
        '  Application files' + #13#10 +
        '    ' + UninstallAppDir + '\       REMOVED' + #13#10 +
        #13#10;

      if UninstallVenvExisted then
      begin
        if UninstallVenvRemoved then
          SummaryMsg := SummaryMsg +
            '  Python virtual environment       REMOVED' + #13#10 +
            '    ' + UninstallVenvDir + #13#10 + #13#10
        else
          SummaryMsg := SummaryMsg +
            '  Python virtual environment       could not be fully removed' + #13#10 +
            '    ' + UninstallVenvDir + #13#10 +
            '    You may delete this folder manually to free disk space.' + #13#10 + #13#10;
      end;

      if UninstallCfgExisted then
      begin
        if KeepCfg then
          SummaryMsg := SummaryMsg +
            '  Configuration and log files      KEPT (your API key is preserved)' + #13#10 +
            '    ' + UninstallConfigDir + #13#10 + #13#10
        else if UninstallCfgRemoved then
          SummaryMsg := SummaryMsg +
            '  Configuration and log files      REMOVED' + #13#10 +
            '    ' + UninstallConfigDir + #13#10 + #13#10
        else
          SummaryMsg := SummaryMsg +
            '  Configuration and log files      could not be fully removed' + #13#10 +
            '    ' + UninstallConfigDir + #13#10 +
            '    You may delete this folder manually to free disk space.' + #13#10 + #13#10;
      end else
        SummaryMsg := SummaryMsg +
          '  Configuration folder was not found — nothing to remove.' + #13#10 + #13#10;

      SummaryMsg := SummaryMsg +
        '  Shortcuts (if they existed)      REMOVED' + #13#10 +
        '  Add/Remove Programs entry        REMOVED' + #13#10 +
        #13#10 +
        '================================================================' + #13#10 +
        'Python was NOT uninstalled.' + #13#10 +
        'To remove Python: Settings -> Apps -> search "Python"' + #13#10 +
        '================================================================';

      MsgBox(SummaryMsg, mbInformation, MB_OK);
    end;
  end;
end;

[Messages]
WelcomeLabel1=Welcome to Dragon Ball Fusion World Tools Setup
WelcomeLabel2=This wizard will install Dragon Ball Fusion World Tools on your computer.%n%nDBFW Tools scans Dragon Ball Fusion World card photos to extract redemption codes and automatically enters them into the game — no manual typing required.%n%nClick Next to see exactly what will be installed before anything changes on your computer.
FinishedLabel=Dragon Ball Fusion World Tools has been installed successfully.%n%nSee the Installation Summary on the previous page for a complete record of what was installed and where.%n%nOn first launch you will be prompted for a free Google Gemini API key.%n%nGet your free key at: aistudio.google.com
