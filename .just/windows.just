# Windows-specific recipes (PowerShell)

# Copy .env from .env.example
[windows]
env:
    Copy-Item .env.example .env

# Find process listening on port. Usage: just find-port 8000
[windows]
find-port port="8000":
    Get-NetTCPConnection -LocalPort {{port}} -ErrorAction SilentlyContinue | Select-Object -Property LocalAddress, LocalPort, State, OwningProcess

# Kill process on port (with confirmation)
[windows]
[confirm("Kill process on this port? [y/N]")]
kill-port port="8000":
    $conn = Get-NetTCPConnection -LocalPort {{port}} -ErrorAction SilentlyContinue; \
    if ($null -eq $conn) { Write-Host "No process on port {{port}}"; exit 0 } \
    else { Stop-Process -Id $conn.OwningProcess -Force; Write-Host "Killed PID $($conn.OwningProcess)" }

# Open project URL in default browser
[windows]
open url="http://localhost:5173":
    Start-Process "{{url}}"
