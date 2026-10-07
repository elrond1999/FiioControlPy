param([string]$PreviousProjectRoot)
$ErrorActionPreference = 'Stop'
$fiioRoot = Split-Path -Parent $PSScriptRoot
& uv sync --locked --project $fiioRoot
if ($LASTEXITCODE -ne 0) { throw 'uv sync failed.' }
$fiioPython = Join-Path $fiioRoot '.venv\Scripts\pythonw.exe'
$fiioDesktop = [Environment]::GetFolderPath('Desktop')
$fiioShell = New-Object -ComObject WScript.Shell
foreach ($fiioEntry in @(
    @{ Name = 'Connect WH-1000XM5'; Script = 'connect-bt11.py'; Description = 'Connect WH-1000XM5 through FiiO BT11 without a browser' },
    @{ Name = 'FiiO BT11 Control'; Script = 'bt11-control.py'; Description = 'Native BT11 codec, LED, name and pairing settings' }
)) {
    $fiioScript = Join-Path $PSScriptRoot $fiioEntry.Script
    $fiioShortcutPath = Join-Path $fiioDesktop ($fiioEntry.Name + '.lnk')
    $fiioArguments = '"' + $fiioScript + '"'
    if (Test-Path -LiteralPath $fiioShortcutPath) {
        $fiioExisting = $fiioShell.CreateShortcut($fiioShortcutPath)
        $fiioMatchesCurrent = $fiioExisting.TargetPath -eq $fiioPython -and $fiioExisting.Arguments -eq $fiioArguments
        $fiioMatchesPrevious = $false
        if ($PreviousProjectRoot) {
            $fiioOldPython = Join-Path $PreviousProjectRoot '.venv\Scripts\pythonw.exe'
            $fiioOldScript = Join-Path (Join-Path $PreviousProjectRoot 'scripts') $fiioEntry.Script
            $fiioMatchesPrevious = $fiioExisting.TargetPath -eq $fiioOldPython -and $fiioExisting.Arguments -eq ('"' + $fiioOldScript + '"')
        }
        if (-not $fiioMatchesCurrent -and -not $fiioMatchesPrevious) {
            throw "A different shortcut with this name already exists: $fiioShortcutPath"
        }
    }
    $fiioShortcut = $fiioShell.CreateShortcut($fiioShortcutPath)
    $fiioShortcut.TargetPath = $fiioPython
    $fiioShortcut.Arguments = $fiioArguments
    $fiioShortcut.WorkingDirectory = $fiioRoot
    $fiioShortcut.IconLocation = $fiioPython + ',0'
    $fiioShortcut.Description = $fiioEntry.Description
    $fiioShortcut.Save()
    Write-Output "Created $fiioShortcutPath"
}
