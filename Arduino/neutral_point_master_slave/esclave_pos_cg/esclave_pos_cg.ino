#include <Wire.h>

// ---------------------------------------------------------------------------
#define ADRESSE_I2C_ESCLAVE 0x08

const int PIN_POS_CG = A0;
const double ADC_MAX = 1023.0;

// NOUVEAU -- valeur mise a jour en continu dans loop(), lue (pas mesuree)
// dans envoyerPosCg(). volatile car partagee entre le code normal et
// l'interruption I2C.
volatile int pos_cg_cache = 0;

// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);
  Serial.println("ESCLAVE_POS_CG -- demarrage.");

  Wire.begin(ADRESSE_I2C_ESCLAVE);
  Wire.onRequest(envoyerPosCg);

  Serial.print("Pret, adresse I2C esclave = 0x");
  Serial.println(ADRESSE_I2C_ESCLAVE, HEX);
}

// ---------------------------------------------------------------------------
void loop() {
  // NOUVEAU -- la mesure ADC se fait ICI (hors interruption), en continu.
  pos_cg_cache = analogRead(PIN_POS_CG);

  static unsigned long t_last_print = 0;
  if (millis() - t_last_print > 200) {
    t_last_print = millis();
    Serial.print("pos_cg brut=");
    Serial.println(pos_cg_cache);
  }
}

// ---------------------------------------------------------------------------
// MODIFIE -- ne fait plus AUCUNE mesure ADC ici, juste lecture d'une
// variable deja disponible + Wire.write(), operation quasi instantanee.
// Securise le timing du bus I2C (evite tout risque de blocage).
// ---------------------------------------------------------------------------
void envoyerPosCg() {
  int valeur_brute = pos_cg_cache;  // lecture rapide, pas de conversion ADC ici
  Wire.write((valeur_brute >> 8) & 0xFF);
  Wire.write(valeur_brute & 0xFF);
}