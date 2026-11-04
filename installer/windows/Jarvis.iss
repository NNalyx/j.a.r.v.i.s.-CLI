#define AppName "Jarvis Desktop"
#define AppVersion "1.0.3"
#define PayloadDir AddBackslash(SourcePath) + "payload"

[Setup]
AppId={{B31245D1-93F3-4B4B-A6D2-143459A1F6E1}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=NNalyx
DefaultDirName={localappdata}\Programs\Jarvis
DefaultGroupName=Jarvis
UninstallDisplayIcon={app}\jarvis_window_icon.ico
OutputDir=output
OutputBaseFilename=Jarvis-Setup-Windows-x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=lowest
WizardStyle=modern
Compression=lzma2/ultra64
SolidCompression=yes
SetupLogging=yes
CloseApplications=yes
RestartApplications=no
DisableProgramGroupPage=yes
Uninstallable=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные ярлыки:"; Flags: checkedonce

[Dirs]
Name: "{app}\jarvis_agent_images"

[Files]
Source: "{#PayloadDir}\.git\*"; DestDir: "{app}\.git"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Excludes: ".git\*,.gitignore,installer\*,requirements.txt"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "prerequisites\python-installer.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
Source: "prerequisites\git-installer.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall
Source: "prerequisites\webview2-installer.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\Jarvis Desktop"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\jarvis_windows_launcher.pyw"""; WorkingDir: "{app}"; IconFilename: "{app}\jarvis_window_icon.ico"
Name: "{autodesktop}\Jarvis Desktop"; Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\jarvis_windows_launcher.pyw"""; WorkingDir: "{app}"; IconFilename: "{app}\jarvis_window_icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: """{app}\jarvis_windows_launcher.pyw"""; WorkingDir: "{app}"; Description: "Запустить Jarvis Desktop"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\Git"
Type: filesandordirs; Name: "{app}\python"

[Code]
function RunHidden(const Filename, Params, WorkingDir: String; var ErrorText: String): Boolean;
var
  ResultCode: Integer;
begin
  Result := Exec(Filename, Params, WorkingDir, SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if not Result then
    ErrorText := 'Не удалось запустить: ' + Filename
  else if ResultCode <> 0 then
    ErrorText := Format('Команда завершилась с кодом %d: %s', [ResultCode, Filename]);
  Result := Result and (ResultCode = 0);
end;

function WebView2RuntimeInstalled(): Boolean;
var
  Version: String;
  RuntimeId: String;
begin
  RuntimeId := '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  Result :=
    (RegQueryStringValue(HKLM64, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + RuntimeId, 'pv', Version) and (Version <> '')) or
    (RegQueryStringValue(HKLM32, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + RuntimeId, 'pv', Version) and (Version <> '')) or
    (RegQueryStringValue(HKCU64, 'Software\Microsoft\EdgeUpdate\Clients\' + RuntimeId, 'pv', Version) and (Version <> '')) or
    (RegQueryStringValue(HKCU32, 'Software\Microsoft\EdgeUpdate\Clients\' + RuntimeId, 'pv', Version) and (Version <> ''));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ErrorText: String;
  PythonExe: String;
  PythonwExe: String;
  VersionedPythonwExe: String;
  GitInstaller: String;
  PythonInstaller: String;
  WebViewInstaller: String;
begin
  if CurStep = ssPostInstall then begin
    PythonExe := ExpandConstant('{app}\python\python.exe');
    PythonwExe := ExpandConstant('{app}\python\pythonw.exe');
    VersionedPythonwExe := ExpandConstant('{app}\python\pythonw3.12.exe');
    GitInstaller := ExpandConstant('{tmp}\git-installer.exe');
    PythonInstaller := ExpandConstant('{tmp}\python-installer.exe');
    WebViewInstaller := ExpandConstant('{tmp}\webview2-installer.exe');

    if WebView2RuntimeInstalled then
      WizardForm.StatusLabel.Caption := 'WebView2 уже установлен — пропускаем этот шаг…'
    else begin
      WizardForm.StatusLabel.Caption := 'Устанавливаем WebView2 для окна приложения…';
      if not RunHidden(WebViewInstaller, '/silent /install', ExpandConstant('{tmp}'), ErrorText) then
        RaiseException(ErrorText + #13#10 + 'Установка остановлена.');
    end;

    WizardForm.StatusLabel.Caption := 'Устанавливаем Git для автообновлений…';
    if not RunHidden(GitInstaller, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP- /DIR="' + ExpandConstant('{app}\Git') + '"', ExpandConstant('{tmp}'), ErrorText) then
      RaiseException(ErrorText + #13#10 + 'Установка остановлена.');

    WizardForm.StatusLabel.Caption := 'Устанавливаем приватный Python…';
    if not RunHidden(PythonInstaller, '/quiet InstallAllUsers=0 TargetDir="' + ExpandConstant('{app}\python') + '" Include_exe=1 Include_pip=1 Include_launcher=0 PrependPath=0 Shortcuts=0 Include_test=0', ExpandConstant('{tmp}'), ErrorText) then
      RaiseException(ErrorText + #13#10 + 'Установка остановлена.');

    if not FileExists(PythonwExe) and FileExists(VersionedPythonwExe) then
      FileCopy(VersionedPythonwExe, PythonwExe, False);
    if not FileExists(PythonExe) or not FileExists(PythonwExe) then
      RaiseException('Python установился не полностью: не найден python.exe или pythonw.exe в ' + ExpandConstant('{app}\python') + '. Удалите папку Jarvis и запустите установщик снова.');

    WizardForm.StatusLabel.Caption := 'Устанавливаем PyTorch CPU…';
    if not RunHidden(PythonExe, '-m pip install --disable-pip-version-check torch torchaudio --index-url https://download.pytorch.org/whl/cpu', ExpandConstant('{app}'), ErrorText) then
      RaiseException(ErrorText + #13#10 + 'Не удалось установить PyTorch. Проверьте подключение к интернету и запустите установщик ещё раз.');

    WizardForm.StatusLabel.Caption := 'Загружаем компоненты Jarvis. Это может занять несколько минут…';
    if not RunHidden(PythonExe, '-m pip install --disable-pip-version-check -r "' + ExpandConstant('{app}\requirements-windows.txt') + '"', ExpandConstant('{app}'), ErrorText) then
      RaiseException(ErrorText + #13#10 + 'Не удалось установить зависимости Jarvis. Проверьте подключение к интернету и запустите установщик ещё раз.');
  end;
end;
