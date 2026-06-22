/*
  Test du module DFR0971.
*/

#include "DFRobot_GP8403.h"

#define ADRESSE_I2C 0x5F

DFRobot_GP8403 dac(&Wire, ADRESSE_I2C);

void setup() {
  Serial.begin(9600);

  Serial.println("Initialisation du DAC GP8403...");
  while (dac.begin() != 0) {
    Serial.println("  Erreur d'init -- verifiez le cablage ");
    delay(1000);
  }
  Serial.println("DAC initialise avec succes.");

  
  dac.setDACOutRange(dac.eOutputRange5V);

  Serial.println("Test : 2.5V sur le canal 0, 1.0V sur le canal 1");
  dac.setDACOutVoltage(2500, 0);   // canal 0 -> 2.5V 
  dac.setDACOutVoltage(1000, 1);   // canal 1 -> 1.0V

  Serial.println("Verifiez que VOUT0 ~2.5V, VOUT1 ~1.0V ");
}

void loop() {
  // rien : les tensions restent fixees aux valeurs definies dans setup()
}
