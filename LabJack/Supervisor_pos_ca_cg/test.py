"""
Test manuel : pilote FIO4/FIO5 a la demande, pour verifier en direct sur
le moniteur serie Arduino (avec test_pins_securite.ino uploade) que le
changement d'etat est bien recu sur D6/D7.

Usage : tape 0 ou 1 pour FIO4, puis 0 ou 1 pour FIO5, observe le moniteur
serie Arduino a chaque changement.
"""

from labjack import ljm

handle = ljm.openS("T4", "ANY", "ANY")
print("Connecte.")

try:
    while True:
        val_ca = input("Valeur FIO4 (0 ou 1, q pour quitter) : ").strip()
        if val_ca.lower() == "q":
            break
        val_cg = input("Valeur FIO5 (0 ou 1) : ").strip()

        ljm.eWriteName(handle, "FIO4", int(val_ca))
        ljm.eWriteName(handle, "FIO5", int(val_cg))
        print(f"FIO4={val_ca}  FIO5={val_cg}  -- verifie le moniteur serie Arduino maintenant")
finally:
    ljm.close(handle)
    print("Ferme.")