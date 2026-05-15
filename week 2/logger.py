import logging
import sys

# ─────────────────────────────────────────────
#  Central logging configuration
#  Import this in every other file like:
#  from logger import logger
# ─────────────────────────────────────────────

# Create a logger with the name "app"
logger = logging.getLogger("app")

# Set the minimum level of messages to record
# DEBUG < INFO < WARNING < ERROR < CRITICAL
logger.setLevel(logging.DEBUG)

# ── Format ──────────────────────────────────
# This defines how each log line looks:
# [2026-05-08 17:30:00] INFO     database.py : Connection established
formatter = logging.Formatter(
    fmt="[%(asctime)s] %(levelname)-8s %(filename)-15s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# ── Handler 1: Print logs to the terminal ───
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)

# ── Handler 2: Save logs to a file ──────────
# All logs are also saved to app.log
# Useful for production monitoring
file_handler = logging.FileHandler("app.log")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

# ── Attach both handlers to the logger ──────
logger.addHandler(console_handler)
logger.addHandler(file_handler)