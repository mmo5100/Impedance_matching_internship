from labjack import ljm
import time

handle = ljm.openS("T4", "USB", "ANY")

# Impose "x" V sur DAC0 et DAC1
ljm.eWriteName(handle, "DAC0", 2.5)

ljm.eWriteName(handle, "DAC1", 3)

# Lit AIN0 (pile) et AIN1 (fil DAC0->AIN1) en boucle
while True:
    values = ljm.eReadNames(handle, 4, ["AIN0", "AIN1", "AIN2", "AIN3"])
    print(f"AIN0 (pile) = {values[0]:.4f} V    AIN1 (DAC0) = {values[1]:.4f} V     AIN2(DAC1) = {values[2]:.4f} V   AIN3 = {values[3]:.4f} V")
    time.sleep(0.5)