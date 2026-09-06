$Task="TV Manager"
if (Get-ScheduledTask -TaskName $Task -ErrorAction SilentlyContinue) {
  Unregister-ScheduledTask -TaskName $Task -Confirm:$false
  Write-Host "TV Manager startup task removed." -ForegroundColor Green
} else {
  Write-Host "TV Manager startup task is not installed."
}
