# Notes Pipeline launcher (Windows PowerShell)
#
#   .\run.ps1                # live mode, needs DEEPSEEK_API_KEY
#   .\run.ps1 -Mock          # no API calls, click through the UI
#   .\run.ps1 -Port 8770
#
param(
  [int]$Port = 8765,
  [switch]$Mock,
  [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = 'C:\Users\Hitesh\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }

if (-not $Mock -and -not $env:DEEPSEEK_API_KEY) {
  Write-Host ''
  Write-Host 'DEEPSEEK_API_KEY is not set.' -ForegroundColor Yellow
  Write-Host '  $env:DEEPSEEK_API_KEY = "sk-..."   then run again' -ForegroundColor Yellow
  Write-Host '  or start in mock mode:  .\run.ps1 -Mock' -ForegroundColor Yellow
  Write-Host ''
}

$args = @((Join-Path $here 'server.py'), '--port', $Port)
if ($Mock) { $args += '--mock' }
if ($NoBrowser) { $args += '--no-browser' }

& $py @args
