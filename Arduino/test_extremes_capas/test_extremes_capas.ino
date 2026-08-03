/*
 * Test de mouvement -- Ca et Cg font une rampe lente entre X_MIN_MM et
 * X_MAX_MM, en boucle, SANS aucun calcul d'eps/asservissement.
 *
 * Objectif : valider toute la chaine mecanique (DAC GP8403 -> Copley 306
 * -> condensateur) independamment de la boucle de controle, en verifiant
 * simplement que Ca et Cg parcourent bien toute leur plage utile.
 *
 * Cablage attendu (identique a neutral_point.ino) :
 *   Vout0 du GP8403 -> Ca (condensateur cote ANTENNE)
 *   Vout1 du GP8403 -> Cg (condensateur cote GENERATEUR)
 */

#include "DFRobot_GP8403.h"

#define ADRESSE_I2C_DAC 0x5F
DFRobot_GP8403 dac(&Wire, ADRESSE_I2C_DAC);

const int CANAL_CA = 0;   // Vout0 -> Ca (cote ANTENNE)
const int CANAL_CG = 1;   // Vout1 -> Cg (cote GENERATEUR)

// Fins de course (a cabler en pull-up, LOW = fin de course atteinte)
const int PIN_ENDSW_CA_MIN = 2;
const int PIN_ENDSW_CA_MAX = 3;
const int PIN_ENDSW_CG_MIN = 4;
const int PIN_ENDSW_CG_MAX = 5;

// Plage de test (memes valeurs que neutral_point.ino, a adapter si besoin)
const double X_MIN_MM = 10.0;
const double X_MAX_MM = 50.0;

// Vitesse de la rampe (mm/s) -- volontairement lente pour observer visuellement
const double RAMP_SPEED_MM_S = 5.0;

// Pause en butee avant de repartir dans l'autre sens (ms)
const unsigned long HOLD_MS = 1000;

// Pile soustractive (meme principe que neutral_point.ino)
const double OFFSET_PILE_V = 3.0;
const double DAC_VREF_V    = 10.0;

// --- Etat interne ---
double pos_a_mm = X_MIN_MM;
double pos_g_mm = X_MIN_MM;
int direction = +1;              // +1 = vers X_MAX_MM, -1 = vers X_MIN_MM
unsigned long t_prev_ms = 0;
bool holding = false;
unsigned long hold_start_ms = 0;

void setup() {
  Serial.begin(115200);

  Serial.println("Initialisation du DAC GP8403...");
  while (dac.begin() != 0) {
    Serial.println("  Erreur d'init -- verifiez le cablage I2C et l'adresse.");
    delay(1000);
  }
  dac.setDACOutRange(dac.eOutputRange5V);
  Serial.println("DAC initialise avec succes.");

  pinMode(PIN_ENDSW_CA_MIN, INPUT_PULLUP);
  pinMode(PIN_ENDSW_CA_MAX, INPUT_PULLUP);
  pinMode(PIN_ENDSW_CG_MIN, INPUT_PULLUP);
  pinMode(PIN_ENDSW_CG_MAX, INPUT_PULLUP);

  Serial.println("Debut du test : rampe X_MIN_MM <-> X_MAX_MM");
  t_prev_ms = millis();
}

// --- Conversion position -> tension DAC (fallback non calibre, identique a
//     neutral_point.ino, recale pour ne pas clipper avec l'offset pile) ---
void outputPosition(double pos_mm, int canal) {
  double frac = (pos_mm - X_MIN_MM) / (X_MAX_MM - X_MIN_MM);
  frac = constrain(frac, 0.0, 1.0);
  double v_reel = -OFFSET_PILE_V + frac * DAC_VREF_V;
  double v_dac = constrain(v_reel + OFFSET_PILE_V, 0.0, DAC_VREF_V);
  dac.setDACOutVoltage((int)(v_dac * 1000.0), canal);
}

void loop() {
  unsigned long t_now_ms = millis();
  double dt_s = (t_now_ms - t_prev_ms) / 1000.0;
  t_prev_ms = t_now_ms;
  if (dt_s <= 0.0 || dt_s > 0.5) return;

  if (holding) {
    // On attend HOLD_MS a la butee avant de repartir
    if (t_now_ms - hold_start_ms >= HOLD_MS) {
      holding = false;
      direction = -direction;
      Serial.print("Reprise du mouvement, direction=");
      Serial.println(direction);
    }
  } else {
    double deplacement = direction * RAMP_SPEED_MM_S * dt_s;
    pos_a_mm += deplacement;
    pos_g_mm += deplacement;

    // Fins de course : on s'arrete si on les atteint (securite hardware)
    bool endsw_ca = (direction > 0) ? (digitalRead(PIN_ENDSW_CA_MAX) == LOW)
                                     : (digitalRead(PIN_ENDSW_CA_MIN) == LOW);
    bool endsw_cg = (direction > 0) ? (digitalRead(PIN_ENDSW_CG_MAX) == LOW)
                                     : (digitalRead(PIN_ENDSW_CG_MIN) == LOW);

    bool bord_atteint = (pos_a_mm >= X_MAX_MM) || (pos_a_mm <= X_MIN_MM) || endsw_ca || endsw_cg;

    pos_a_mm = constrain(pos_a_mm, X_MIN_MM, X_MAX_MM);
    pos_g_mm = constrain(pos_g_mm, X_MIN_MM, X_MAX_MM);

    if (bord_atteint) {
      holding = true;
      hold_start_ms = t_now_ms;
      Serial.println("Butee atteinte, pause...");
    }
  }

  outputPosition(pos_a_mm, CANAL_CA);
  outputPosition(pos_g_mm, CANAL_CG);

  static unsigned long t_last_print = 0;
  if (t_now_ms - t_last_print > 100) {
    t_last_print = t_now_ms;
    Serial.print("x_a_mm="); Serial.print(pos_a_mm, 3);
    Serial.print(" x_g_mm="); Serial.print(pos_g_mm, 3);
    Serial.print(" | endsw_CA_min="); Serial.print(digitalRead(PIN_ENDSW_CA_MIN));
    Serial.print(" endsw_CA_max="); Serial.print(digitalRead(PIN_ENDSW_CA_MAX));
    Serial.print(" endsw_CG_min="); Serial.print(digitalRead(PIN_ENDSW_CG_MIN));
    Serial.print(" endsw_CG_max="); Serial.println(digitalRead(PIN_ENDSW_CG_MAX));
  }
}
