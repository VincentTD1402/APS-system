# Unix-specific recipes (macOS / Linux)

# Copy .env from .env.example
[unix]
env:
    cp .env.example .env

# Find process listening on port. Usage: just find-port 8000
[unix]
find-port port="8000":
    lsof -i tcp:{{port}}

# Kill process on port (with confirmation)
[unix]
[confirm("Kill process on this port? [y/N]")]
kill-port port="8000":
    #!/usr/bin/env bash
    pids=$(lsof -t -i tcp:{{port}})
    if [ -z "$pids" ]; then
        echo "No process on port {{port}}"
        exit 0
    fi
    echo "Killing PIDs: $pids"
    kill $pids

# Open project URL in default browser (macOS/Linux)
[unix]
open url="http://localhost:5173":
    #!/usr/bin/env bash
    if command -v open >/dev/null 2>&1; then
        open "{{url}}"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "{{url}}"
    else
        echo "Open manually: {{url}}"
    fi
