#!/usr/bin/env bash
# ==============================================================================
# Arb Cannon: M&A Leak Arbitrage Command Center — 5:00 PM EST Automation Setup
#
# Configures:
#   1. Antigravity Scheduled Automation (~/.gemini/config/sidecars/arb-cannon-nightly-mailer/sidecar.json)
#   2. macOS launchd plist (~/Library/LaunchAgents/com.arbcannon.nightly.plist)
#   3. Fallback weekday 5:00 PM EST crontab command (CRON_TZ=America/New_York 0 17 * * 1-5)
# ==============================================================================

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PROJECT_DIR}/.venv/bin/python"
if [ ! -x "${PYTHON_BIN}" ]; then
  PYTHON_BIN="$(command -v python3)"
fi

PLIST_DIR="${HOME}/Library/LaunchAgents"
PLIST_PATH="${PLIST_DIR}/com.arbcannon.nightly.plist"
LOG_DIR="${PROJECT_DIR}/logs"

mkdir -p "${PLIST_DIR}" "${LOG_DIR}"

cat > "${PLIST_PATH}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.arbcannon.nightly</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_BIN}</string>
        <string>${PROJECT_DIR}/nightly_mailer.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${PROJECT_DIR}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>TZ</key>
        <string>America/New_York</string>
    </dict>
    <key>StartCalendarInterval</key>
    <array>
        <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>17</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Weekday</key><integer>2</integer><key>Hour</key><integer>17</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Weekday</key><integer>3</integer><key>Hour</key><integer>17</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Weekday</key><integer>4</integer><key>Hour</key><integer>17</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Weekday</key><integer>5</integer><key>Hour</key><integer>17</integer><key>Minute</key><integer>0</integer></dict>
    </array>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/nightly_mailer.out.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/nightly_mailer.err.log</string>
</dict>
</plist>
EOF

echo "=============================================================================="
echo "ARB CANNON 5:00 PM EST NIGHTLY AUTOMATION CONFIGURED"
echo "=============================================================================="
echo "1. Antigravity Scheduled Automation Sidecar:"
echo "   ~/.gemini/config/sidecars/arb-cannon-nightly-mailer/sidecar.json"
echo "   Schedule: CRON_TZ=America/New_York 0 17 * * 1-5"
echo ""
echo "2. macOS launchd plist written to:"
echo "   ${PLIST_PATH}"
echo "   To load via launchctl:"
echo "   launchctl unload \"${PLIST_PATH}\" 2>/dev/null || true && launchctl load \"${PLIST_PATH}\""
echo ""
echo "3. Equivalent Crontab Entry (5:00 PM EST Mon-Fri):"
echo "   CRON_TZ=America/New_York"
echo "   0 17 * * 1-5 cd \"${PROJECT_DIR}\" && \"${PYTHON_BIN}\" \"${PROJECT_DIR}/nightly_mailer.py\" >> \"${LOG_DIR}/cron.log\" 2>&1"
echo "=============================================================================="
