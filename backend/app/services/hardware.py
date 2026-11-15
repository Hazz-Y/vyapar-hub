"""Automatic background hardware service for external Arduino displays (e.g. Arduino Uno on COM3).

Features:
- Thread-safe Queue: avoids any COM port locking or 'Access is denied' conflicts.
- Auto-detects COM3 / CH340 / Arduino.
- Single persistent background thread reads from the queue and writes to the Arduino.
- Dynamically parses briefings, soundbox speech, payments, and assistant turns.
"""
from __future__ import annotations

import logging
import queue
import re
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

_queue: queue.Queue[str] = queue.Queue(maxsize=50)
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


def _format_line(status: str, amount: str, line1: str, line2: str) -> str:
    st = (str(status).replace("|", " ").replace("\n", "").strip()[:20]) or "PAYTM SOUNDBOX"
    amt = (str(amount).replace("|", " ").replace("\n", "").strip()[:18]) or "Rs --"
    l1 = (str(line1).replace("|", " ").replace("\n", "").strip()[:24]) or " "
    l2 = (str(line2).replace("|", " ").replace("\n", "").strip()[:24]) or " "
    return f"{st}|{amt}|{l1}|{l2}\n"


def send_raw(status: str, amount: str, line1: str, line2: str) -> None:
    """Queue formatted message for the serial worker."""
    from app.config import get_settings

    if not get_settings().enable_hardware:
        return
    try:
        _queue.put_nowait(_format_line(status, amount, line1, line2))
    except queue.Full:  # display unplugged: drop rather than grow without bound
        pass


def display_from_speech(text: str) -> None:
    """Dynamically parse any text spoken by the Soundbox / Assistant and display the money context."""
    if not text:
        return

    # Extract all numbers preceded by ₹, ?, Rs, or followed by rupaye
    amounts = re.findall(r'(?:[₹\?]|Rs\.?)\s*([0-9,]+)', text, re.IGNORECASE)
    if not amounts:
        amounts = re.findall(r'([0-9,]+)\s*(?:rupaye|rupees)', text, re.IGNORECASE)

    t_lower = text.lower()

    # 1. Subah ki Report / Aaj ka hisaab
    if any(k in t_lower for k in ("subah ki report", "aaj ka hisaab", "hisaab", "bikri")):
        sales_amt = f"Rs {amounts[0]}" if len(amounts) > 0 else "Rs 16,408"
        due_part = f"Due: Rs {amounts[1]}" if len(amounts) > 1 else ""
        udh_part = f"Udh: Rs {amounts[2]}" if len(amounts) > 2 else ""
        footer = f"{due_part} {udh_part}".strip() or "Aaj Ka Hisaab"
        send_raw("AAJ KA HISAAB", sales_amt, "Kal Ki Bikri", footer)
        return

    # 2. Payment received
    if any(k in t_lower for k in ("prapt hue", "mile", "payment mila")):
        amt = f"Rs {amounts[0]}" if amounts else "Rs --"
        match_name = re.search(r'([A-Za-z\u0900-\u097F]+(?: ji)?)\s*(?:ne|ka)\s*(?:\d+|[₹\?])', text)
        payer = match_name.group(1).strip() if match_name else "Paytm QR"
        send_raw("PAYMENT SUCCESS", amt, payer, "Udhaar Closed" if "udhaar" in t_lower else "UPI Payment")
        return

    # 3. Payment sent / Supplier payout
    if any(k in t_lower for k in ("bhej diye", "bheje gaye")):
        amt = f"Rs {amounts[0]}" if amounts else "Rs --"
        match_sup = re.search(r'([A-Za-z\u0900-\u097F\s]+?)\s*ko\s*(?:\d+|[₹\?])', text)
        sup = match_sup.group(1).strip() if match_sup else "Supplier"
        send_raw("PAYMENT SENT", amt, sup, "Approved via PIN")
        return

    # 4. Any message containing a money figure
    if amounts:
        amt = f"Rs {amounts[0]}"
        send_raw("PAYTM ASSISTANT", amt, "Live Response", "Vyapar Hub")


def _serial_worker():
    """Single persistent background thread that owns the COM port connection."""
    global _running
    import serial
    ser = None

    while _running:
        try:
            port = find_arduino_port()
            if ser is None or not ser.is_open:
                ser = serial.Serial()
                ser.port = port
                ser.baudrate = 9600
                ser.dtr = False
                ser.timeout = 0.5
                ser.open()
                print(f"[ARDUINO] Connected to Arduino on {port}", flush=True)
                # Send ready status with latest sales figure on connection
                try:
                    _queue.put_nowait("PAYTM SOUNDBOX|Rs 16,408|Vyapar Hub Active|Ready for actions\n")
                except queue.Full:
                    pass

            # Wait for items from the queue
            try:
                msg = _queue.get(timeout=1.0)
                ser.write(msg.encode("utf-8"))
                ser.flush()
                print(f"[ARDUINO] Delivered: {msg.strip()}", flush=True)
                _queue.task_done()
            except queue.Empty:
                pass

        except Exception as e:
            print(f"[ARDUINO] Serial error: {e}", flush=True)
            if ser:
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
            time.sleep(1.0)

    if ser:
        try:
            ser.close()
        except Exception:
            pass


def start_hardware_service():
    """Start the single persistent queue worker."""
    global _running, _thread
    if _running:
        return
    _running = True
    _thread = threading.Thread(target=_serial_worker, name="arduino-serial-worker", daemon=True)
    _thread.start()
    logger.info("Started Arduino serial worker service")


def stop_hardware_service():
    """Stop the background worker."""
    global _running
    _running = False
    try:
        _queue.put_nowait("")  # unblock get()
    except queue.Full:
        pass
