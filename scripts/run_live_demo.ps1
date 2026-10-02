# Live public demo: A-RWMF server + free Cloudflare quick tunnel.
# Prints a shareable https:// URL that scores ANY website through this machine.
#
#   scripts\run_live_demo.cmd     (double-click / run from terminal)
#
# - Takes over port 5000 (stops any other listener there).
# - Server output is captured to page_captures\server.*.log for debugging.
# - If the server dies, it is restarted automatically (up to 3 times).
# - Ctrl+C stops the tunnel and the server.
$ErrorActionPreference = "Stop"
$root    = Split-Path -Parent $PSScriptRoot
$base    = "http://127.0.0.1:5000"
$cfExe   = Join-Path $root "tools\cloudflared.exe"
$outLog  = Join-Path $env:TEMP "arwmf-tunnel.out"
$errLog  = Join-Path $env:TEMP "arwmf-tunnel.err"
$srvOut  = Join-Path $root "page_captures\server.out.log"
$srvErr  = Join-Path $root "page_captures\server.err.log"
$demoLog = Join-Path $root "page_captures\live_demo.log"
New-Item -ItemType Directory -Force (Join-Path $root "page_captures") | Out-Null

function Log($msg) {
    $line = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $msg
    Write-Host $line
    Add-Content -Path $demoLog -Value $line
}

function Start-Server {
    # take over port 5000 so this script fully owns the server lifecycle
    $owner = (Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue |
              Select-Object -First 1).OwningProcess
    if ($owner) {
        Stop-Process -Id $owner -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 1
    }
    $p = Start-Process python -ArgumentList (Join-Path $root "webapp\server.py") -PassThru `
        -WindowStyle Hidden -RedirectStandardOutput $srvOut -RedirectStandardError $srvErr
    foreach ($i in 1..40) {
        Start-Sleep -Milliseconds 500
        $h = (curl.exe -s --max-time 3 "$base/api/health") -join ""
        if ($h -match '"ok"\s*:\s*true') { return @{ Proc = $p; Ok = $true } }
    }
    return @{ Proc = $p; Ok = $false }
}

# --- one-time: fetch cloudflared -------------------------------------------
if (-not (Test-Path $cfExe)) {
    Write-Host "Downloading cloudflared (one-time, ~30 MB)..."
    New-Item -ItemType Directory -Force (Split-Path $cfExe) | Out-Null
    curl.exe -L --fail -o $cfExe "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    if (-not (Test-Path $cfExe)) { throw "cloudflared download failed" }
}

# --- server -----------------------------------------------------------------
Log "starting server on :5000"
$s = Start-Server
if (-not $s.Ok) {
    if ($s.Proc -and !$s.Proc.HasExited) { Stop-Process -Id $s.Proc.Id -Force }
    throw "server did not become healthy - see $srvErr"
}
$srv = $s.Proc
Log "server ready (pid $($srv.Id))"

# --- tunnel -----------------------------------------------------------------
Remove-Item $outLog, $errLog -ErrorAction SilentlyContinue
$tun = $null
try {
    Log "opening cloudflare tunnel"
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
    if (-not $url) { throw "tunnel URL not found - see $errLog" }
    Log "tunnel ready: $url"

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

    # stay alive until Ctrl+C; auto-restart the server if it dies
    $miss = 0
    $restarts = 0
    while ($true) {
        if ($tun.HasExited) { throw "tunnel exited (code $($tun.ExitCode))" }
        $h = (curl.exe -s --max-time 3 "$base/api/health") -join ""
        if ($h -notmatch '"ok"\s*:\s*true') {
            $miss++
            if ($miss -ge 5) {
                $miss = 0
                $restarts++
                if ($restarts -gt 3) { throw "server keeps dying (3 restarts) - see $srvErr" }
                Log "server not answering - restarting ($restarts of 3)"
                $s = Start-Server
                if ($s.Ok) { $srv = $s.Proc; Log "server back up (pid $($srv.Id))" }
            }
        } else {
            $miss = 0
        }
        Start-Sleep -Seconds 10
    }
}
finally {
    Log "stopping"
    if ($tun -and !$tun.HasExited) { Stop-Process -Id $tun.Id -Force -ErrorAction SilentlyContinue }
    Stop-Process -Name cloudflared -Force -ErrorAction SilentlyContinue
    if ($srv -and !$srv.HasExited) { Stop-Process -Id $srv.Id -Force -ErrorAction SilentlyContinue }
}
