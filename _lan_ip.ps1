# Prints the primary LAN IPv4 address (the interface with a default gateway).
# Used by start-ui.bat to build a reachable API base for remote browsers.
$cfg = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -ne $null -and $_.NetAdapter.Status -eq 'Up' }
$ip = ($cfg | Select-Object -First 1).IPv4Address.IPAddress
if ($ip) { Write-Output $ip } else { Write-Output "127.0.0.1" }
