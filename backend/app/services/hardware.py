"""Automatic hardware display service for external Arduino displays (e.g. Arduino Uno on COM3).

Fully dynamic:
- Auto-detects COM3 / CH340 / Arduino.
- ZERO hardcoded figures: dynamically parses whatever action or speech is triggered.
- Listens to:
  * 'Aaj ka hisaab' (Subah ki Report) -> extracts real sales, payables due, and udhaar collection.
  * Payment received (QR simulation, customer udhaar repayment) -> extracts amount and payer name.
  * Payment sent (Supplier payout approved via PIN) -> extracts amount and vendor name.
  * Voice / chat assistant responses -> extracts any live money figure mentioned.
"""
from __future__ import annotations

import logging
import re
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


def _format_line(status: str, amount: str, line1: str, line2: str) -> str:
    st = str(status).replace("|", " ").replace("\n", "").strip()[:20]
    amt = str(amount).replace("|", " ").replace("\n", "").strip()[:18]
    l1 = str(line1).replace("|", " ").replace("\n", "").strip()[:24]
    l2 = str(line2).replace("|", " ").replace("\n", "").strip()[:24]
    return f"{st}|{amt}|{l1}|{l2}\n"


def send_raw(status: str, amount: str, line1: str, line2: str) -> None:
    """Send formatted text to the Arduino over Serial without blocking."""
    def _worker():
        try:
            import serial
            port = find_arduino_port()
            with serial.Serial(port=port, baudrate=9600, dtr=False, timeout=0.5) as s:
                line = _format_line(status, amount, line1, line2)
                s.write(line.encode("utf-8"))
                s.flush()
                logger.info("Sent to Arduino: %s", line.strip())
        except Exception as e:
            logger.debug("Failed writing to Arduino: %s", e)

    threading.Thread(target=_worker, daemon=True).start()


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
    if "subah ki report" in t_lower or "aaj ka hisaab" in t_lower or "hisaab" in t_lower or "bikri" in t_lower:
        sales_amt = f"Rs {amounts[0]}" if len(amounts) > 0 else "Rs --"
        due_part = f"Due: Rs {amounts[1]}" if len(amounts) > 1 else ""
        udh_part = f"Udh: Rs {amounts[2]}" if len(amounts) > 2 else ""
        footer = f"{due_part} {udh_part}".strip() or "Aaj Ka Hisaab"
        send_raw("AAJ KA HISAAB", sales_amt, "Kal Ki Bikri", footer)
        return

    # 2. Payment received
    if "prapt hue" in t_lower or "mile" in t_lower or "payment mila" in t_lower:
        amt = f"Rs {amounts[0]}" if amounts else "Rs --"
        match_name = re.search(r'([A-Za-z\u0900-\u097F]+(?: ji)?)\s*(?:ne|ka)\s*(?:\d+|[₹\?])', text)
        payer = match_name.group(1).strip() if match_name else "Paytm QR"
        send_raw("PAYMENT SUCCESS", amt, payer, "Udhaar Closed" if "udhaar" in t_lower else "UPI Payment")
        return

    # 3. Payment sent / Supplier payout
    if "bhej diye" in t_lower or "bheje gaye" in t_lower:
        amt = f"Rs {amounts[0]}" if amounts else "Rs --"
        match_sup = re.search(r'([A-Za-z\u0900-\u097F\s]+?)\s*ko\s*(?:\d+|[₹\?])', text)
        sup = match_sup.group(1).strip() if match_sup else "Supplier"
        send_raw("PAYMENT SENT", amt, sup, "Approved via PIN")
        return

    # 4. Any message containing a money figure
    if amounts:
        amt = f"Rs {amounts[0]}"
        send_raw("PAYTM ASSISTANT", amt, "Live Response", "Vyapar Hub")


def _hardware_worker():
    global _running
    import serial
    ser = None

    while _running:
        try:
            port = find_arduino_port()
            if ser is None or not ser.is_open:
                ser = serial.Serial(port=port, baudrate=9600, dtr=False, timeout=0.5)
                logger.info("Connected to Arduino on %s", port)
        except Exception:
            if ser:
                try:
                    ser.close()
                except Exception:
                    pass
                ser = None
        time.sleep(2.0)

    if ser:
        try:
            ser.close()
        except Exception:
            pass


def start_hardware_service():
    global _running, _thread
    if _running:
        return
    _running = True
    _thread = threading.Thread(target=_hardware_worker, name="arduino-hardware-service", daemon=True)
    _thread.start()


def stop_hardware_service():
    global _running
    _running = False
