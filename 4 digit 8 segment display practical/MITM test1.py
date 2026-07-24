import time
import tm1637

# Initialize the display (GND, VCC=3.3V, Example Pins are DIO-20 and CLK21)
Display = tm1637.TM1637(CLK=21, DIO=20, brightness=1.0)

# Display all digits at a time
digits = [1, 2, 3, 4]
Display.Show(digits)

time.sleep(5)
Display.Clear()

# Display digits one by one
Display.Show1(0, 1)
time.sleep(1)
Display.Show1(1, 2)
time.sleep(1)
Display.Show1(2, 3)
time.sleep(1)
Display.Show1(3, 4)
time.sleep(1)

# Add colon in between
Display.ShowDoublepoint(True)
time.sleep(5)

# Controll Brightness
Display.SetBrightness(0)
time.sleep(1)
Display.SetBrightness(0.2)
time.sleep(1)
Display.SetBrightness(0.4)
time.sleep(1)
Display.SetBrightness(0.6)
time.sleep(1)
Display.SetBrightness(0.8)
time.sleep(1)
Display.SetBrightness(1)
time.sleep(5)

Display.SetBrightness(0.8)
time.sleep(1)
Display.SetBrightness(0.6)
time.sleep(1)
Display.SetBrightness(0.4)
time.sleep(1)
Display.SetBrightness(0.2)
time.sleep(1)
Display.SetBrightness(0)
time.sleep(1)
Display.Clear()