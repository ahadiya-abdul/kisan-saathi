"""Launcher for the preserved Flask prototype of the updated copy (port 5010).

NEW file; does not change app.py. Note: in this snapshot the Flask page's chat
JavaScript is not wired up (see docs/STAGE_A_AUDIT.md).
"""
import os

from app import app

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("FIELDWISE_FLASK_PORT", "5010")), debug=True)
