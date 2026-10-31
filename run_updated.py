"""Launcher for the *updated working copy* of Fieldwise.

Runs the canonical FastAPI app (backend.main:app) on a DIFFERENT port than the
original project so both can run side by side:

    original FastAPI  -> http://127.0.0.1:8000
    original Flask    -> http://127.0.0.1:5000
    updated copy      -> http://127.0.0.1:8010   (this script)

Override with:  set FIELDWISE_PORT=8020   (Windows cmd)
                $env:FIELDWISE_PORT = "8020"  (PowerShell)

This file is NEW and does not change any existing code.
"""
import os

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("FIELDWISE_PORT", "8010"))
    uvicorn.run("backend.main:app", host="127.0.0.1", port=port, reload=True)
