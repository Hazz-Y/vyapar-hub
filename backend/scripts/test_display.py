"""Test sending transaction or briefing data to the Arduino Uno on COM3."""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.hardware import send_to_display

mode = sys.argv[1] if len(sys.argv) > 1 else "briefing"

if mode == "briefing":
    print("Testing Briefing (Aaj ka hisaab) display...")
    send_to_display(16408, "Kal Bikri (Aaj Ka Hisaab)", "Pay Due: Rs 13800", status="SUBAH KI REPORT")
else:
    print("Testing Payment display...")
    send_to_display(650.00, "Sunita", "UPI TXN: 116580", status="PAYMENT SUCCESS")

time.sleep(0.5)
print("Sent! Check Display 2.")
