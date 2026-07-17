# Windows-specific recipes for aps-backend (PowerShell)

# Create Python venv via uv
[windows]
venv:
    uv venv

# Copy .env from .env.example
[windows]
env:
    Copy-Item .env.example .env

# Add runtime dependency. Usage: just add fastapi
[windows]
add *deps:
    uv add {{deps}}

# Add dev dependency
[windows]
add-dev *deps:
    uv add --dev {{deps}}

# Remove dependency
[windows]
remove *deps:
    uv remove {{deps}}

# Find process listening on port
[windows]
find-port port="8000":
    Get-NetTCPConnection -LocalPort {{port}} -ErrorAction SilentlyContinue | Select-Object -Property LocalAddress, LocalPort, State, OwningProcess

# Kill process on port
[windows]
[confirm("Kill process on this port? [y/N]")]
kill-port port="8000":
    $conn = Get-NetTCPConnection -LocalPort {{port}} -ErrorAction SilentlyContinue; \
    if ($null -eq $conn) { Write-Host "No process on port {{port}}"; exit 0 } \
    else { Stop-Process -Id $conn.OwningProcess -Force; Write-Host "Killed PID $($conn.OwningProcess)" }
