"""Test sending transaction data directly to the Arduino Uno on COM3."""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.hardware import send_to_display

amount = float(sys.argv[1]) if len(sys.argv) > 1 else 650.00
name = sys.argv[2] if len(sys.argv) > 2 else "Sunita"
txn_id = sys.argv[3] if len(sys.argv) > 3 else "DEMO10293"

print(f"Sending to Arduino: Rs {amount:.2f} | {name} | UPI TXN: {txn_id}")
send_to_display(amount, name, txn_id)
time.sleep(0.5)
print("Sent! Check Display 2 on your Arduino Uno.")
