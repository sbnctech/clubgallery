#!/usr/bin/env python3
"""
Face Recognition Health Check Script

Monitors the face recognition service and sends email alerts when it's down.
Designed to run via cron every 5 minutes.

Cron entry:
*/5 * * * * /opt/sbnc-photos/scripts/face_recognition_health_check.py
"""

import sys
import json
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

# Configuration
HEALTH_CHECK_URL = "http://127.0.0.1:5199/api/health"
ALERT_RECIPIENTS = ["technology@sbnewcomers.org", "sbnctech@gmail.com"]
FROM_EMAIL = "noreply@sbnewcomers.org"
STATE_FILE = "/opt/sbnc-photos/data/health_check_state.json"
TIMEOUT_SECONDS = 10

# How many consecutive failures before alerting
FAILURE_THRESHOLD = 2

# How long (minutes) between repeat alerts for ongoing issues
REPEAT_ALERT_INTERVAL = 60


def load_state():
    """Load previous state from file."""
    state_path = Path(STATE_FILE)
    if state_path.exists():
        try:
            with open(state_path) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "consecutive_failures": 0,
        "last_alert_time": None,
        "last_status": "unknown",
        "last_error": None
    }


def save_state(state):
    """Save state to file."""
    state_path = Path(STATE_FILE)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(state_path, 'w') as f:
        json.dump(state, f, indent=2)


def check_service():
    """
    Check if the face recognition service is responding.
    Returns (is_healthy, error_message)
    """
    try:
        response = requests.get(HEALTH_CHECK_URL, timeout=TIMEOUT_SECONDS)
        if response.status_code == 200:
            data = response.json()
            if data.get('face_recognition', {}).get('available'):
                return True, None
            else:
                return False, f"Face recognition unavailable: {data.get('face_recognition', {}).get('error', 'Unknown error')}"
        else:
            return False, f"HTTP {response.status_code}: {response.text[:100]}"
    except requests.exceptions.ConnectionError:
        return False, "Connection refused - service not running"
    except requests.exceptions.Timeout:
        return False, f"Request timed out after {TIMEOUT_SECONDS}s"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"


def send_alert(subject, body):
    """Send email alert to configured recipients."""
    try:
        # Use local sendmail (server has postfix configured)
        msg = MIMEMultipart()
        msg['From'] = FROM_EMAIL
        msg['To'] = ', '.join(ALERT_RECIPIENTS)
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        # Connect to local SMTP server
        with smtplib.SMTP('localhost') as server:
            server.sendmail(FROM_EMAIL, ALERT_RECIPIENTS, msg.as_string())

        print(f"Alert sent: {subject}")
        return True
    except Exception as e:
        print(f"Failed to send alert: {e}", file=sys.stderr)
        return False


def send_down_alert(error_message, consecutive_failures):
    """Send alert that service is down."""
    subject = "[ALERT] SBNC Face Recognition Service DOWN"
    body = f"""SBNC Photo Gallery Alert

The face recognition service is not responding.

Status: DOWN
Error: {error_message}
Consecutive failures: {consecutive_failures}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Server: mail.sbnewcomers.org

Actions to take:
1. SSH to server: ssh -p 7822 root@mail.sbnewcomers.org
2. Check service status: systemctl status sbnc-photos
3. View logs: journalctl -u sbnc-photos -n 50
4. Restart service: systemctl restart sbnc-photos

The photo editor interface will continue to work but face detection
and recognition features will be unavailable until the service is restored.

This is an automated message from the SBNC Photo Gallery System.
"""
    return send_alert(subject, body)


def send_recovery_alert():
    """Send alert that service has recovered."""
    subject = "[RESOLVED] SBNC Face Recognition Service RECOVERED"
    body = f"""SBNC Photo Gallery Alert

The face recognition service has recovered and is now operational.

Status: UP
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Server: mail.sbnewcomers.org

No action required. Face recognition features are now available.

This is an automated message from the SBNC Photo Gallery System.
"""
    return send_alert(subject, body)


def main():
    state = load_state()
    is_healthy, error_message = check_service()

    now = datetime.now().isoformat()

    if is_healthy:
        # Service is up
        if state["last_status"] == "down" and state["consecutive_failures"] >= FAILURE_THRESHOLD:
            # Was down, now recovered - send recovery alert
            send_recovery_alert()

        state["consecutive_failures"] = 0
        state["last_status"] = "up"
        state["last_error"] = None
        print(f"[{now}] Face recognition service: OK")

    else:
        # Service is down
        state["consecutive_failures"] += 1
        state["last_error"] = error_message

        print(f"[{now}] Face recognition service: DOWN ({error_message})")

        should_alert = False

        if state["consecutive_failures"] == FAILURE_THRESHOLD:
            # Just hit threshold - send initial alert
            should_alert = True
        elif state["consecutive_failures"] > FAILURE_THRESHOLD:
            # Already alerting - check if we should send repeat alert
            if state["last_alert_time"]:
                last_alert = datetime.fromisoformat(state["last_alert_time"])
                minutes_since_alert = (datetime.now() - last_alert).total_seconds() / 60
                if minutes_since_alert >= REPEAT_ALERT_INTERVAL:
                    should_alert = True

        if should_alert:
            if send_down_alert(error_message, state["consecutive_failures"]):
                state["last_alert_time"] = now

        state["last_status"] = "down"

    save_state(state)


if __name__ == '__main__':
    main()
