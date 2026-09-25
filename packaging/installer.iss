#define AppName "Hair Class Organizer"
#define Artifact "Hair-Class-Organizer-" + AppVersion + "-windows-amd64"

[Setup]
AppId=electblake.Hair-Class-Organizer
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=electblake
DefaultDirName={localappdata}\Programs\Hair-Class-Organizer
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=no
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename={#Artifact}-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
SetupLogging=yes

[Files]
Source: "..\build\bootstrap\uv\uv.exe"; DestDir: "{app}\tools"; Flags: ignoreversion
Source: "..\build\bootstrap\LICENSE-*"; DestDir: "{app}\tools\licenses"; Flags: ignoreversion
Source: "..\app\*.py"; DestDir: "{app}\app\app"; Flags: ignoreversion
Source: "..\app\models\*.py"; DestDir: "{app}\app\app\models"; Flags: ignoreversion
Source: "..\pyproject.toml"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\uv.lock"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "install-runtime.cmd"; DestDir: "{app}"; Flags: ignoreversion

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "explorer"; Description: "Add to File Explorer context menu"; GroupDescription: "Windows integration"; Flags: checkedonce

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\runtime\venv\Scripts\pythonw.exe"; Parameters: "-I -m app"; WorkingDir: "{app}\app"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\runtime\venv\Scripts\pythonw.exe"; Parameters: "-I -m app"; WorkingDir: "{app}\app"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Classes\Directory\shell\HairClassOrganizer"; ValueType: string; ValueName: ""; ValueData: "Organize hair color"; Flags: uninsdeletekey; Tasks: explorer
Root: HKCU; Subkey: "Software\Classes\Directory\shell\HairClassOrganizer\command"; ValueType: string; ValueName: ""; ValueData: """{app}\runtime\venv\Scripts\pythonw.exe"" -I -m app ""%1"""; Tasks: explorer
Root: HKCU; Subkey: "Software\Classes\*\shell\HairClassOrganizer"; ValueType: string; ValueName: ""; ValueData: "Organize hair color"; Flags: uninsdeletekey; Tasks: explorer
Root: HKCU; Subkey: "Software\Classes\*\shell\HairClassOrganizer\command"; ValueType: string; ValueName: ""; ValueData: """{app}\runtime\venv\Scripts\pythonw.exe"" -I -m app ""%1"""; Tasks: explorer

[Run]
Filename: "{app}\runtime\venv\Scripts\pythonw.exe"; Parameters: "-I -m app"; WorkingDir: "{app}\app"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent; Check: DependenciesInstalled

[UninstallDelete]
Type: filesandordirs; Name: "{app}\runtime"
Type: filesandordirs; Name: "{app}\app\hair_class_organizer.egg-info"
Type: filesandordirs; Name: "{app}\app\build"

[Code]
var
  DependencyExitCode: Integer;
  DependencyLog: TNewMemo;

procedure InitializeWizard;
begin
  DependencyLog := TNewMemo.Create(WizardForm);
  DependencyLog.Parent := WizardForm.InstallingPage;
  DependencyLog.SetBounds(0, ScaleY(100), WizardForm.InstallingPage.Width,
    WizardForm.InstallingPage.Height - ScaleY(100));
  DependencyLog.ReadOnly := True;
  DependencyLog.ScrollBars := ssVertical;
end;

procedure DependencyOutput(const S: String; const Error, FirstLine: Boolean);
begin
  Log(S);
  DependencyLog.Lines.Add(S);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    WizardForm.StatusLabel.Caption := 'Installing Python, the private virtual environment, and model runtime dependencies...';
    ExecAndLogOutput(ExpandConstant('{cmd}'),
      '/D /C ""' + ExpandConstant('{app}\install-runtime.cmd') + '""',
      ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, DependencyExitCode, @DependencyOutput);
    Log('Dependency setup exit code: ' + IntToStr(DependencyExitCode));
  end;
end;

function DependenciesInstalled: Boolean;
begin
  Result := DependencyExitCode = 0;
end;

function GetCustomSetupExitCode: Integer;
begin
  Result := DependencyExitCode;
end;
