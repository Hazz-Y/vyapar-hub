"""Automatic background hardware service for external Arduino displays (e.g. Arduino Uno on COM3).

Features:
- Runs automatically when backend starts up.
- Auto-detects CH340 / Arduino / USB Serial ports (defaults to COM3).
- On launch, fetches the latest transaction from the database and displays it immediately.
- Continually watches the database for any new transactions (QR payment, demo, supplier payout)
  and pushes them to Display 2 over Serial.
- Reconnects automatically if the USB cable is unplugged/plugged in.
- Non-blocking daemon: never slows down or crashes FastAPI.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

_running = False
_thread: Optional[threading.Thread] = None


def find_arduino_port() -> str:
    """Find the COM port for Arduino Uno / CH340, defaulting to COM3."""
    try:
        import serial.tools.list_ports
        for p in serial.tools.list_ports.comports():
            desc = (p.description or "").lower()
            hwid = (p.hwid or "").lower()
            if any(k in desc or k in hwid for k in ("ch340", "arduino", "usb-serial", "usb serial")):
                return p.device
    except Exception:
        pass
    return "COM3"


def _format_txn_line(amount: float | int, counterparty: str | None, txn_id: int | str) -> str:
    name = str(counterparty or "PAYTM QR").replace("|", " ").replace("\n", "").strip()[:20]
    tx = str(txn_id).replace("|", " ").replace("\n", "").strip()[:18]
    return f"Rs {float(amount):.2f}|{name}|UPI TXN: {tx}\n"


def _hardware_worker():
    global _running
    import serial
    from app.db import get_engine
    from app.models import Transaction
    from sqlmodel import Session, select

    ser = None
    last_txn_id = 0

    # On startup, fetch current highest transaction ID so we display it immediately
    try:
        with Session(get_engine()) as session:
            latest = session.exec(select(Transaction).order_by(Transaction.id.desc())).first()
            if latest:
                last_txn_id = latest.id
    except Exception as e:
        logger.debug("Hardware worker initial query failed: %s", e)

    displayed_initial = False

    while _running:
        port = find_arduino_port()
        try:
            if ser is None or not ser.is_open:
                ser = serial.Serial()
                ser.port = port
                ser.baudrate = 9600
                ser.dtr = False
                ser.timeout = 0.5
                ser.open()
                logger.info("Connected to Arduino display on %s", port)
                displayed_initial = False

            # Display initial/latest transaction upon connection
            if not displayed_initial and last_txn_id > 0:
                with Session(get_engine()) as session:
                    txn = session.get(Transaction, last_txn_id)
                    if txn:
                        line = _format_txn_line(txn.amount, txn.counterparty, txn.id)
                        ser.write(line.encode("utf-8"))
                        ser.flush()
                displayed_initial = True

            # Poll for new transactions
            with Session(get_engine()) as session:
                new_txns = session.exec(
                    select(Transaction)
                    .where(Transaction.id > last_txn_id)
                    .order_by(Transaction.id)
                ).all()

                for txn in new_txns:
                    line = _format_txn_line(txn.amount, txn.counterparty, txn.id)
                    ser.write(line.encode("utf-8"))
                    ser.flush()
                    last_txn_id = txn.id
                    time.sleep(0.3)

        except Exception as e:
            logger.debug("Hardware display loop exception (will retry): %s", e)
            if ser:
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
            displayed_initial = False

        time.sleep(1.0)

    if ser:
        try:
            ser.close()
        except Exception:
            pass


def start_hardware_service():
    """Start the automatic hardware background monitor."""
    global _running, _thread
    if _running:
        return
    _running = True
    _thread = threading.Thread(target=_hardware_worker, name="arduino-hardware-display", daemon=True)
    _thread.start()
    logger.info("Started automatic Arduino display service")


def stop_hardware_service():
    """Stop the background monitor."""
    global _running
    _running = False


def send_to_display(amount: int | float, name: str, txn_id: int | str) -> None:
    """Explicit push if needed; the background poller will also pick up DB transactions."""
    try:
        import serial
        port = find_arduino_port()
        with serial.Serial(port=port, baudrate=9600, dtr=False, timeout=0.5) as s:
            line = _format_txn_line(amount, name, txn_id)
            s.write(line.encode("utf-8"))
            s.flush()
    except Exception:
        pass
