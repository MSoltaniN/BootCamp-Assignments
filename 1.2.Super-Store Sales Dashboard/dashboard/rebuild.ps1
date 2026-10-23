# Rebuild the Superstore BI dashboard end to end.
#
#   CSV -> aggregates (pandas) -> self-contained HTML -> PDF + PNG (Chrome)
#
# Usage:
#   .\rebuild.ps1                 # build + export
#   .\rebuild.ps1 -NoExport       # HTML only (fast loop while editing)
#   .\rebuild.ps1 -Verify         # also cross-check the browser's numbers

param(
    [switch]$NoExport,
    [switch]$Verify
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$out = Join-Path $here 'out'
$py = 'C:\Users\pc\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path -LiteralPath $py)) { $py = 'python' }

$chrome = @(
    'C:\Program Files\Google\Chrome\Application\chrome.exe',
    'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

$sw = [Diagnostics.Stopwatch]::StartNew()

Write-Host '== 1/4  build html ==' -ForegroundColor Cyan
& $py (Join-Path $here 'build.py') --answers
if ($LASTEXITCODE -ne 0) { throw 'build.py failed' }

if ($NoExport) { $sw.Stop(); Write-Host ("done in {0:N1}s (html only)" -f $sw.Elapsed.TotalSeconds) -ForegroundColor Green; return }

if (-not $chrome) { throw 'Chrome not found; cannot export' }

$html = Join-Path $out 'dashboard.html'
$uri = 'file:///' + ($html -replace '\\', '/' -replace ' ', '%20')
$common = @('--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
    '--disable-lcd-text', '--font-render-hinting=none', '--virtual-time-budget=12000',
    '--window-size=1680,1050')

# Chrome may detach from the launching shell, so never trust the exit code:
# run it, then wait for the artifact to appear and stop growing.
# Paths here contain spaces, so every switch is quoted before it reaches Chrome;
# otherwise one token becomes two arguments ("multiple targets" in headless).
function ConvertTo-ChromeArgString {
    param([string[]]$Items)
    return (($Items | ForEach-Object {
        if ($_ -match '\s') { '"' + $_ + '"' } else { $_ }
    }) -join ' ')
}

function Invoke-ChromeExport {
    param([string]$Target, [string[]]$Extra, [int]$TimeoutSec = 90)

    if (Test-Path -LiteralPath $Target) { Remove-Item -LiteralPath $Target }
    $argStr = ConvertTo-ChromeArgString -Items @($common + $Extra)
    $p = Start-Process -FilePath $chrome -ArgumentList $argStr -PassThru -WindowStyle Hidden `
        -RedirectStandardError (Join-Path $out 'chrome.err.log')
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    $lastSize = -1
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Milliseconds 250
        if (Test-Path -LiteralPath $Target) {
            $size = (Get-Item -LiteralPath $Target).Length
            if ($size -gt 0 -and $size -eq $lastSize) { break }
            $lastSize = $size
        }
    }
    if (-not $p.HasExited) { try { $p.WaitForExit(5000) | Out-Null } catch { } }
    if (-not (Test-Path -LiteralPath $Target)) {
        $err = Join-Path $out 'chrome.err.log'
        if (Test-Path $err) { Get-Content $err -Tail 6 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray } }
        throw "export failed: $Target"
    }
}

Write-Host '== 2/4  export pdf ==' -ForegroundColor Cyan
$pdf = Join-Path $out 'dashboard.pdf'
Invoke-ChromeExport -Target $pdf -Extra @('--no-pdf-header-footer', "--print-to-pdf=$pdf", $uri)
'{0:N0} KiB' -f ((Get-Item $pdf).Length / 1KB) | ForEach-Object { "  pdf  $_" }

Write-Host '== 3/4  export png ==' -ForegroundColor Cyan
$png = Join-Path $out 'dashboard.png'
Invoke-ChromeExport -Target $png -Extra @('--force-device-scale-factor=2', "--screenshot=$png", $uri)
Add-Type -AssemblyName System.Drawing
$img = [System.Drawing.Image]::FromFile($png)
"  png  {0} KiB  {1}x{2}" -f [int]((Get-Item $png).Length / 1KB), $img.Width, $img.Height
$img.Dispose()

if ($Verify) {
    Write-Host '== 4/4  verify browser figures against pandas ==' -ForegroundColor Cyan
    $dom = Join-Path $out 'dom.html'
    if (Test-Path -LiteralPath $dom) { Remove-Item -LiteralPath $dom }
    $p = Start-Process -FilePath $chrome -ArgumentList (ConvertTo-ChromeArgString -Items @($common + @('--dump-dom', $uri))) -PassThru `
        -WindowStyle Hidden -RedirectStandardOutput $dom -RedirectStandardError (Join-Path $out 'chrome.dom.err.log')
    $p.WaitForExit(90000) | Out-Null
    & $py (Join-Path $here 'verify.py') $dom
    if ($LASTEXITCODE -ne 0) { throw 'browser figures do not match the pandas reference' }
}
else {
    Write-Host '== 4/4  verify skipped (-Verify to run) ==' -ForegroundColor DarkGray
}

$sw.Stop()
Write-Host ("done in {0:N1}s" -f $sw.Elapsed.TotalSeconds) -ForegroundColor Green
