"""
Test a blanc de la communication serie avec l'Arduino (accord_servo.ino),
SANS avoir besoin des servomoteurs branches.

Envoie quelques commandes connues et affiche la reponse de l'Arduino pour verifier que
le parsing et les bornes (0-180 deg) fonctionnent comme attendu.

Attention pour utiliser ce script il faut fermer l'IDE Arduino.
"""

import time
import serial

PORT = "COM5"   # A MODIFIER : voir Outils > Port dans l'IDE Arduino
BAUD = 9600

# (angle_a envoye, angle_g envoye) -- inclut des valeurs hors plage pour
# verifier le clipping (200 -> doit redevenir 180.0, -10 -> 0.0)
COMMANDES_TEST = [
    (90.0, 45.0),
    (0.0, 180.0),
    (200.0, -10.0),   
]

ser = serial.Serial(PORT, BAUD, timeout=2)
time.sleep(2)  # laisser le temps a l'Arduino de redemarrer

print(f"Port {PORT} ouvert. Lecture du message de demarrage :")
print(" ", ser.readline().decode(errors="replace").strip())

for angle_a, angle_g in COMMANDES_TEST:
    trame = f"{angle_a},{angle_g}\n"
    ser.write(trame.encode())
    reponse = ser.readline().decode(errors="replace").strip()
    print(f"Envoye : {trame.strip():<20}  ->  Recu : {reponse}")

ser.close()
print("\nPort serie ferme.")