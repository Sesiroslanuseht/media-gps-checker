param([string]$ExifToolDirectory = '')
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if ($env:OS -ne 'Windows_NT') { throw 'Build on Windows 10/11 x64; PyInstaller is not a cross-compiler.' }
function Check-Exit { if ($LASTEXITCODE -ne 0) { throw "Command failed with exit code $LASTEXITCODE" } }
if (!(Test-Path '.venv-build\Scripts\python.exe')) { py -3.12 -m venv .venv-build; Check-Exit }
$Python = (Resolve-Path '.venv-build\Scripts\python.exe').Path
& $Python -m pip install -r requirements-build.txt
Check-Exit
$env:QT_QPA_PLATFORM = 'offscreen'
if ($ExifToolDirectory) {
    $ExifToolDirectory = (Resolve-Path $ExifToolDirectory).Path
    if (!(Test-Path (Join-Path $ExifToolDirectory 'exiftool.exe'))) { throw 'Rename exiftool(-k).exe to exiftool.exe first.' }
    if (!(Test-Path (Join-Path $ExifToolDirectory 'exiftool_files'))) { throw 'Keep the full official exiftool_files folder.' }
    $env:EXIFTOOL_TEST_PATH = Join-Path $ExifToolDirectory 'exiftool.exe'
}
& $Python -m unittest discover -s tests -v
Check-Exit
& $Python -m PyInstaller --noconfirm --clean --onedir --windowed --name MediaGPSChecker run_gui.py
Check-Exit
$Target = 'dist\MediaGPSChecker'
Copy-Item README.md, WINDOWS_BUILD.md, THIRD_PARTY.md, LICENSE, requirements*.txt -Destination $Target
if ($ExifToolDirectory) { Copy-Item -Recurse $ExifToolDirectory (Join-Path $Target 'exiftool') }
& $Python scripts\copy_licenses.py $Target
Check-Exit
& $Python -m pip freeze | Out-File (Join-Path $Target 'build-environment.txt') -Encoding utf8
# The exe imports Qt and checks an optional bundled ExifTool without opening a native window.
$SmokePath = Join-Path (Resolve-Path $Target).Path 'smoke-result.txt'
$Process = Start-Process -FilePath (Join-Path (Resolve-Path $Target).Path 'MediaGPSChecker.exe') -ArgumentList @('--self-test', ('"' + $SmokePath + '"')) -Wait -PassThru
if ($Process.ExitCode -ne 0) { throw 'Frozen smoke test failed.' }
if (!(Test-Path (Join-Path $Target 'smoke-result.txt'))) { throw 'Frozen smoke test did not produce its marker.' }
Compress-Archive -Path $Target -DestinationPath 'dist\MediaGPSChecker-Windows-x64.zip' -Force
Write-Host 'Created dist\MediaGPSChecker-Windows-x64.zip'
