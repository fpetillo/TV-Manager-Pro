param([string]$BaseUrl = "http://127.0.0.1:5050")
$ErrorActionPreference="Stop"
try {
  $health = Invoke-RestMethod -Uri "$BaseUrl/api/health" -TimeoutSec 10
  Write-Host "TV Manager: reachable" -ForegroundColor Green
  $health | ConvertTo-Json -Depth 5
} catch {
  Write-Host "TV Manager: not reachable at $BaseUrl" -ForegroundColor Red
  Write-Host $_.Exception.Message
  exit 1
}
