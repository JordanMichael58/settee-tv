# Settee TV installer for Windows 7 SP1 to 11. Needs PowerShell 2.0 or newer and no admin rights.
# install.bat runs it. Options: -DryRun (only print what would happen), -NoStartup, -NoDesktop, -Uninstall.
param([switch]$DryRun, [switch]$NoStartup, [switch]$NoDesktop, [switch]$Uninstall)
$ErrorActionPreference = 'Stop'

$src = Split-Path -Parent $MyInvocation.MyCommand.Definition
$root = Join-Path $env:LOCALAPPDATA 'SetteeTV'
$app = Join-Path $root 'app'
$embed = Join-Path $root 'python'
$pyUrl = 'https://www.python.org/ftp/python/3.8.10/python-3.8.10-embed-win32.zip'
$links = @((Join-Path ([Environment]::GetFolderPath('Startup')) 'Settee TV.lnk'),
           (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Settee TV.lnk'))

function Step($text, [scriptblock]$work) {
    if ($DryRun) { Write-Host "[dry run] $text" } else { Write-Host $text; & $work }
}

function Stop-Settee {
    # Only the processes started as "python -m settee", never other Python programs.
    Get-WmiObject Win32_Process -Filter "CommandLine LIKE '%-m settee%'" | ForEach-Object { [void]$_.Terminate() }
}

function Test-Python($exe, $pre) {
    try {
        $out = & $exe @pre -c "import sys; print(sys.executable if sys.version_info >= (3, 8) else '')" 2>$null
    } catch { return $null }
    if ($LASTEXITCODE -eq 0 -and $out) { return ([string]$out).Trim() }
    return $null
}

function Get-EmbeddedPython {
    $exe = Join-Path $embed 'python.exe'
    if (Test-Path $exe) { return $exe }
    Step "Python 3.8 was not found. Downloading Python 3.8.10 (about 7 MB) from python.org into $embed" {
        try {
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]3072  # TLS 1.2
        } catch {
            throw "This PC cannot use TLS 1.2 (it needs .NET Framework 4.5 or newer). Install Python 3.8 from python.org yourself, then run install.bat again."
        }
        New-Item -ItemType Directory -Force -Path $embed | Out-Null
        $zip = Join-Path $root 'python-embed.zip'
        (New-Object Net.WebClient).DownloadFile($pyUrl, $zip)
        $shell = New-Object -ComObject Shell.Application
        $shell.Namespace($embed).CopyHere($shell.Namespace($zip).Items(), 20)  # 4 + 16: no dialog, yes to all
        for ($i = 0; $i -lt 120 -and -not (Test-Path $exe); $i++) { Start-Sleep -Milliseconds 500 }
        Remove-Item $zip
        if (-not (Test-Path $exe)) { throw "Unpacking Python failed. Install Python 3.8 from python.org yourself, then run install.bat again." }
        # The embedded Python only looks in the folders its ._pth file names: add the app folder.
        Add-Content -Path (Join-Path $embed 'python38._pth') -Value $app
    }
    return $exe
}

if ($Uninstall) {
    Step "Stopping Settee TV" { Stop-Settee }
    foreach ($l in $links) { if (Test-Path $l) { Step "Removing $l" { Remove-Item $l } } }
    foreach ($d in @($app, $embed)) { if (Test-Path $d) { Step "Removing $d" { Remove-Item -Recurse -Force $d } } }
    if (-not $DryRun) { Write-Host "Settee TV is removed." }
    Write-Host " Your settings stay in $(Join-Path $root 'data'); delete that folder too if you want."
    exit 0
}

if (-not (Test-Path (Join-Path $src 'settee\__main__.py'))) { throw "Run install.ps1 from the Settee TV folder (settee\ is missing next to it)." }

$py = Test-Python 'py' @('-3')
if (-not $py) { $py = Test-Python 'python' @() }
if (-not $py) { $py = Get-EmbeddedPython }
Write-Host "Python: $py"
$pyw = Join-Path (Split-Path -Parent $py) 'pythonw.exe'
if (-not (Test-Path $pyw)) { $pyw = $py }

Step "Stopping an older Settee TV, if one runs" { Stop-Settee }
Step "Copying the program to $app" {
    if (Test-Path $app) { Remove-Item -Recurse -Force $app }
    New-Item -ItemType Directory -Force -Path $app | Out-Null
    foreach ($part in @('settee', 'web', 'LICENSE')) { Copy-Item -Recurse (Join-Path $src $part) $app }
    Get-ChildItem -Recurse -Force $app | Where-Object { $_.PSIsContainer -and $_.Name -eq '__pycache__' } | Remove-Item -Recurse -Force
}

$wanted = @()
if (-not $NoStartup) { $wanted += $links[0] }
if (-not $NoDesktop) { $wanted += $links[1] }
foreach ($l in $wanted) {
    Step "Shortcut: $l" {
        $s = (New-Object -ComObject WScript.Shell).CreateShortcut($l)
        $s.TargetPath = $pyw
        $s.Arguments = '-m settee'
        $s.WorkingDirectory = $app
        $s.Description = 'Settee TV'
        $s.Save()
    }
}

Step "Starting Settee TV" { Start-Process -FilePath $pyw -ArgumentList '-m settee' -WorkingDirectory $app }
Write-Host ""
Write-Host "Done. If Windows asks whether Python may use the network, allow PRIVATE networks only: that lets phones on your Wi-Fi reach the remote."
Write-Host "Settings (on this PC): http://127.0.0.1:4960/settings"
