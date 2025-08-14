import datetime

import time
import tm1637

# Initialize the display (GND, VCC=3.3V, Example Pins are DIO-20 and CLK21)
Display = tm1637.TM1637(CLK=21, DIO=20, brightness=1.0)

currentDateTime = datetime.datetime.now()
date = currentDateTime.date()
year = date.strftime("%Y")

#for i in range(4):
#    Display.Show1(i, int(year[i]))
    
Display.Show1(0, int(year[0]))
Display.Show1(1, int(year[1]))
Display.Show1(2, int(year[2]))
Display.Show1(3, int(year[3]))

time.sleep(5)

Display.Clear()
