from rfid_pi5 import SimpleRC522

rfid = SimpleRC522()

print("Hold your tag near the reader to scan...")
uid, text = rfid.read()

if uid:
    print(f"Card UID : {uid}")
    print(f"Data Read: '{text}'")
else:
    print("No card detected within timeout.")