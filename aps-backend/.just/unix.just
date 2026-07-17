# Unix-specific recipes for aps-backend (macOS / Linux)

# Create Python venv via uv
[unix]
venv:
    uv venv

# Copy .env from .env.example
[unix]
env:
    cp .env.example .env

# Add runtime dependency. Usage: just add fastapi
[unix]
add *deps:
    uv add {{deps}}

# Add dev dependency
[unix]
add-dev *deps:
    uv add --dev {{deps}}

# Remove dependency
[unix]
remove *deps:
    uv remove {{deps}}

# Find process listening on port
[unix]
find-port port="8000":
    lsof -i tcp:{{port}}

# Kill process on port
[unix]
[confirm("Kill process on this port? [y/N]")]
kill-port port="8000":
    #!/usr/bin/env bash
    pids=$(lsof -t -i tcp:{{port}})
    if [ -z "$pids" ]; then
        echo "No process on port {{port}}"; exit 0
    fi
    echo "Killing PIDs: $pids"
    kill $pids
