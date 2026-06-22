/*
  Pilotage de 2 servos (Ca, Cg) par liaison serie.

  Format attendu, une ligne par commande, terminee par '\n' :
      angle_a,angle_g
  ex : "90.0,45.5\n"

  Cablage : mettre Servo Ca à pin D9 et Servo Cg à pin D10

 Ce sketch se contente de recevoir une position cible et de l'appliquer.
*/

#include <Servo.h>

Servo servoA;
Servo servoG;

const int PIN_SERVO_A = 9;
const int PIN_SERVO_G = 10;

void setup() {
  Serial.begin(9600);
  servoA.attach(PIN_SERVO_A);
  servoG.attach(PIN_SERVO_G);
  Serial.println("Pret. Envoyez une ligne 'angle_a,angle_g' (ex: 90,45.5)");
}

void loop() {
  if (Serial.available() > 0) {
    String ligne = Serial.readStringUntil('\n');
    int idx = ligne.indexOf(',');
    if (idx > 0) {
      float angleA = ligne.substring(0, idx).toFloat();
      float angleG = ligne.substring(idx + 1).toFloat();
      angleA = constrain(angleA, 0.0, 180.0);
      angleG = constrain(angleG, 0.0, 180.0);
      servoA.write((int)angleA);
      servoG.write((int)angleG);
      // Retour console -- permet de verifier la reception/parsing SANS
      // avoir besoin des servos branches (juste le cable USB).
      Serial.print("OK angle_a=");
      Serial.print(angleA);
      Serial.print(" angle_g=");
      Serial.println(angleG);
    } else {
      Serial.print("Ligne invalide (pas de virgule) : ");
      Serial.println(ligne);
    }
  }
}
