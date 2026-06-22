/*
  Pilotage du DAC DFR0971 (2 canaux) par liaison serie.
*/

#include "DFRobot_GP8403.h"

#define ADRESSE_I2C 0x5F
#define V_MIN 0.0
#define V_MAX 10.0

DFRobot_GP8403 dac(&Wire, ADRESSE_I2C);

void setup() {
  Serial.begin(9600);
  while (!Serial) {}

  Serial.println("Initialisation du DAC GP8403...");
  while (dac.begin() != 0) {
    Serial.println("  Erreur d'init -- verifiez le cablage I2C et l'adresse.");
    delay(1000);
  }
  dac.setDACOutRange(dac.eOutputRange10V);
  Serial.println("Pret. Envoyez une ligne 'tension_a,tension_b' en V (ex: 2.5,1.0)");
}

void loop() {
  if (Serial.available() > 0) {
    String ligne = Serial.readStringUntil('\n');
    int idx = ligne.indexOf(',');
    if (idx > 0) {
      float v_a = ligne.substring(0, idx).toFloat();
      float v_b = ligne.substring(idx + 1).toFloat();
      v_a = constrain(v_a, V_MIN, V_MAX);
      v_b = constrain(v_b, V_MIN, V_MAX);

      dac.setDACOutVoltage((int)(v_a * 1000), 0);  // valeur en mV, canal 0
      dac.setDACOutVoltage((int)(v_b * 1000), 1);  // valeur en mV, canal 1

      // Retour console 
      Serial.print("OK v_out_0=");
      Serial.print(v_a);
      Serial.print("V  v_out_1=");
      Serial.print(v_b);
      Serial.println("V");
    } else {
      Serial.print("Ligne invalide : ");
      Serial.println(ligne);
    }
  }
}
