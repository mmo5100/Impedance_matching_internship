/*
  Test de cablage -- balayage simple de 2 servos (Ca, Cg)
  Avant de brancher la vraie trajectoire (accord_servo.ino), verifiez que
  les deux servos bougent correctement avec ce sketch.

  Cablage :
    servo Ca : signal -> pin 9,  alim -> 5V,  masse -> GND
    servo Cg : signal -> pin 10, alim -> 5V,  masse -> GND
  ATTENTION : si les servos bougent par saccades ou si l'Arduino "reset"
  tout seul, c'est generalement un probleme d'alimentation -- alimentez les
  servos par une source 5V externe (pas seulement le 5V de l'Arduino),
  masse commune avec l'Arduino.
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
}

void loop() {
  for (int angle = 10; angle <= 170; angle += 1) {
    servoA.write(angle);
    servoG.write(180 - angle);  // sens oppose, pour bien voir les 2 bouger independamment
    Serial.print("angle_a=");
    Serial.print(angle);
    Serial.print(" angle_g=");
    Serial.println(180 - angle);
    delay(15);
  }
  for (int angle = 170; angle >= 10; angle -= 1) {
    servoA.write(angle);
    servoG.write(180 - angle);
    Serial.print("angle_a=");
    Serial.print(angle);
    Serial.print(" angle_g=");
    Serial.println(180 - angle);
    delay(15);
  }
}
