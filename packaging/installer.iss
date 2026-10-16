; Установщик DevOps Academy (Inno Setup 6).
; Сборка в CI:  iscc /DAppVersion=1.2.3 /DBuildNumber=42 packaging/installer.iss
;
; Поддерживает тихую установку, которую запускает автообновление из приложения:
;   DevOpsAcademy-Setup-1.2.3.exe /SILENT /SUPPRESSMSGBOXES /NOCANCEL /RESTARTAPPLICATIONS

#define AppName "DevOps Academy"
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef BuildNumber
  #define BuildNumber "0"
#endif
#define AppExe "DevOpsAcademy.exe"
#define AppId "{{B7B3F1B0-6C7B-4C5B-9F1F-DEVOPSACADEMY}}"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion} (build {#BuildNumber})
AppPublisher=DevOps Academy
DefaultDirName={autopf}\DevOpsAcademy
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=DevOpsAcademy-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayIcon={app}\{#AppExe}
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\DevOpsAcademy\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Удалить {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Запустить {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\content"
