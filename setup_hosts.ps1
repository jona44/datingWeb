# Requires Administrator elevation to modify Windows hosts file
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "Requesting Administrator privileges to update hosts file..." -ForegroundColor Cyan
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

$hostsPath = "$env:windir\System32\drivers\etc\hosts"
$content = Get-Content -Path $hostsPath -Raw -ErrorAction Stop

$entriesToAdd = @()
if ($content -notmatch '(?m)^\s*127\.0\.0\.1\s+hivplus\.local') {
    $entriesToAdd += "127.0.0.1    hivplus.local"
}
if ($content -notmatch '(?m)^\s*127\.0\.0\.1\s+diversehearts\.local') {
    $entriesToAdd += "127.0.0.1    diversehearts.local"
}

if ($entriesToAdd.Count -eq 0) {
    Write-Host "Hostnames are already configured in $hostsPath!" -ForegroundColor Green
} else {
    $newLines = "`r`n`r`n# Dating-webapp Variant Hostnames`r`n" + ($entriesToAdd -join "`r`n") + "`r`n"
    [System.IO.File]::AppendAllText($hostsPath, $newLines, [System.Text.Encoding]::ASCII)
    Write-Host "Successfully added entries to ${hostsPath}:" -ForegroundColor Green
    $entriesToAdd | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
}

Write-Host "Flushing DNS resolver cache..." -ForegroundColor Cyan
ipconfig /flushdns | Out-Null

Write-Host "`nSetup complete! You can now access:" -ForegroundColor Green
Write-Host "  - http://hivplus.local:8000        (HIV+ Community variant)" -ForegroundColor White
Write-Host "  - http://diversehearts.local:8000 (Diverse Hearts variant)`n" -ForegroundColor White

Write-Host "Press any key to close..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
