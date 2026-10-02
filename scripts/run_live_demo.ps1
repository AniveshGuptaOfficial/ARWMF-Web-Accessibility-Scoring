# Start the live A-RWMF server + a free Cloudflare quick tunnel, print the
# public URL anyone can use to score ANY website from your machine.
#
#   scripts\run_live_demo.cmd     (double-click / run from terminal)
#
# Ctrl+C stops both the tunnel and the server.
$ErrorActionPreference = "Stop"
$root   = Split-Path -Parent $PSScriptRoot
$base   = "http://127.0.0.1:5000"
$cfExe  = Join-Path $root "tools\cloudflared.exe"
$outLog = Join-Path $env:TEMP "arwmf-tunnel.out"
$errLog = Join-Path $env:TEMP "arwmf-tunnel.err"

# --- one-time: fetch cloudflared -------------------------------------------
if (-not (Test-Path $cfExe)) {
    Write-Host "Downloading cloudflared (one-time, ~30 MB)..."
    New-Item -ItemType Directory -Force (Split-Path $cfExe) | Out-Null
    curl.exe -L --fail -o $cfExe "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    if (-not (Test-Path $cfExe)) { throw "cloudflared download failed" }
}

# --- server: start our own; only reuse if it proves healthy ----------------
$srv = $null
$health = ""
try {
    Write-Host "Starting A-RWMF server on :5000 ..."
    $srv = Start-Process python -ArgumentList (Join-Path $root "webapp\server.py") `
        -PassThru -WindowStyle Minimized
} catch { }   # if the port is taken, an already-running server may answer below
foreach ($i in 1..40) {
    Start-Sleep -Milliseconds 500
    $health = (curl.exe -s --max-time 3 "$base/api/health") -join ""
    if ($health -match '"ok"\s*:\s*true') { break }
}
if ($health -notmatch '"ok"\s*:\s*true') {
    if ($srv -and !$srv.HasExited) { Stop-Process -Id $srv.Id -Force }
    throw "no healthy server on $base - check that python/webapp/server.py starts"
}
Write-Host "server ready."

# --- tunnel -----------------------------------------------------------------
Remove-Item $outLog, $errLog -ErrorAction SilentlyContinue
$tun = $null
try {
    Write-Host "Opening Cloudflare tunnel..."
    $tun = Start-Process $cfExe -ArgumentList "tunnel","--url",$base,"--no-autoupdate" `
        -PassThru -WindowStyle Hidden `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog

    $url = $null
    foreach ($i in 1..90) {
        Start-Sleep -Seconds 1
        $txt = ""
        if (Test-Path $errLog) { $txt += Get-Content $errLog -Raw -ErrorAction SilentlyContinue }
        if (Test-Path $outLog) { $txt += Get-Content $outLog -Raw -ErrorAction SilentlyContinue }
        if ($txt -match "https://[a-z0-9-]+\.trycloudflare\.com") { $url = $Matches[0]; break }
    }
    if (-not $url) {
        Write-Host "!! tunnel URL not found - logs:"; Get-Content $errLog -ErrorAction SilentlyContinue
        throw "tunnel failed to start"
    }

    Write-Host ""
    Write-Host "============================================================"
    Write-Host "  LIVE DEMO READY - share this link with anyone:"
    Write-Host ""
    Write-Host "    $url"
    Write-Host ""
    Write-Host "  Any URL, real scoring, ~10-60 s (first run warms models)."
    Write-Host "  Keep this window open.  Ctrl+C stops everything."
    Write-Host "============================================================"
    Write-Host ""

    # keep running until Ctrl+C; watch that the server stays alive
    $miss = 0
    while ($true) {
        if ($tun.HasExited) { throw "tunnel exited (code $($tun.ExitCode))" }
        $h = (curl.exe -s --max-time 3 "$base/api/health") -join ""
        if ($h -notmatch '"ok"\s*:\s*true') {
            $miss++
            if ($miss -ge 5) { throw "server stopped answering on $base - run this script again" }
        } else { $miss = 0 }
        Start-Sleep -Seconds 10
    }
}
finally {
    if ($tun -and !$tun.HasExited) { Stop-Process -Id $tun.Id -Force -ErrorAction SilentlyContinue }
    Stop-Process -Name cloudflared -Force -ErrorAction SilentlyContinue
    if ($srv -and !$srv.HasExited) { Stop-Process -Id $srv.Id -Force -ErrorAction SilentlyContinue }
    Write-Host "stopped."
}
