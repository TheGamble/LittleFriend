#!/bin/bash
# system/auto_update.sh

APP_DIR="/home/pi/LittleFriend"
cd "$APP_DIR" || exit 1

# Check network connectivity (wait up to 10s)
for i in {1..10}; do
    if ping -c 1 -W 1 1.1.1.1 &>/dev/null; then break; fi
    sleep 1
done

# Check if origin has new commits
git fetch origin main --quiet
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse @{u})

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "[AutoUpdate] New commit detected. Updating LittleFriend..."
    git reset --hard origin/main
    
    # Update python dependencies if requirements.txt changed
    if git diff --name-only "$LOCAL" HEAD | grep -q "requirements.txt"; then
        "$APP_DIR/venv/bin/pip" install -r requirements.txt --quiet
    fi
    
    # Restart the systemd service to boot into the new code
    sudo systemctl restart littlefriend.service
fi
