import os
import subprocess

import requests


def mac_notification(title: str, message: str) -> None:
    safe_title = title.replace('"', '\\"')
    safe_message = message.replace('"', '\\"')
    script = f'display notification "{safe_message}" with title "{safe_title}" sound name "Glass"'
    try:
        subprocess.run(['osascript', '-e', script], check=False, timeout=5)
    except Exception as e:
        print(f"[notifier] mac notification failed: {e}")


def whatsapp_notification(message: str) -> None:
    url = os.environ.get('TWILIO_WEBHOOK_URL')
    if not url:
        print("[notifier] TWILIO_WEBHOOK_URL not set, skipping WhatsApp")
        return
    try:
        requests.post(
            url,
            json={'message': message, 'source': 'MES Dashboard'},
            timeout=5,
        )
    except Exception as e:
        print(f"[notifier] whatsapp notification failed: {e}")


def notify_task_ready(task_title: str) -> None:
    mac_notification('MES Dashboard — New Task', task_title)


def notify_task_complete(task_title: str, result_summary: str) -> None:
    snippet = (result_summary or '')[:100]
    mac_notification('MES Dashboard — Task Complete', f'{task_title}: {snippet}')
    whatsapp_notification(f'Task complete — {task_title}\n{snippet}')
