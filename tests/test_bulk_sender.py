import asyncio

from teleguard.handlers.bulk_sender import BulkSender


def test_stopped_job_remains_stopped():
    sender = object.__new__(BulkSender)
    job = {
        "status": "stopped",
        "targets": ["target"],
        "sent": 1,
        "total": 3,
        "failed": 0,
    }
    sender.active_jobs = {"job": job}

    async def send_initial_status(_job):
        return None

    async def send_final_status(current_job, _status_msg):
        current_job["final_status"] = current_job["status"]

    sender._send_initial_status = send_initial_status
    sender._send_final_status = send_final_status

    asyncio.run(sender._execute_bulk_job("job", client=None))

    assert job["status"] == "stopped"
    assert job["final_status"] == "stopped"
    assert "job" not in sender.active_jobs


def test_finished_job_reports_real_line_breaks():
    sender = object.__new__(BulkSender)

    class Event:
        text = ""

        async def reply(self, text):
            self.text = text
            return self

    event = Event()
    job = {"event": event, "account_name": "account", "total": 3}

    asyncio.run(sender._send_initial_status(job))

    assert "Campaign Started**\n\nAccount: account\nTotal Users: 3\n" in event.text
    assert "\\n" not in event.text


def test_stopped_job_reports_partial_progress():
    sender = object.__new__(BulkSender)

    class StatusMessage:
        text = ""

        async def edit(self, text):
            self.text = text

    status_msg = StatusMessage()
    job = {
        "status": "stopped",
        "account_name": "account",
        "sent": 1,
        "total": 3,
        "failed": 0,
    }

    asyncio.run(sender._send_final_status(job, status_msg))

    assert "Campaign Stopped" in status_msg.text
    assert "Sent: 1/3" in status_msg.text
    assert "Progress: ■■■░░░░░░░ 33%" in status_msg.text
    assert "\\n" not in status_msg.text
