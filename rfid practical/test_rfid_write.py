from rfid_pi5 import SimpleRC522

rfid = SimpleRC522()

text = input("Enter text : ")
print("Hold your tag near the reader...")

result = rfid.write(text)

if result == True:
    print("Successfully written to tag!")
else:
    print("Failed to write.")