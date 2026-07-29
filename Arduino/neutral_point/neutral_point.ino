/*
 * ============================================================================
 * Recherche du point de matching en fonction de la charge -- adapte aux
 * entrees/sorties REELLEMENT disponibles sur le panneau "AUTOTUNING 32.5 MHz" :
 *
 *   ENTREES (BNC sur le panneau)  : VA, VG, V+, VA-V+, VG-V+
 *   SORTIES (BNC sur le panneau)  : CA, CG   (consignes de position)
 *
 * Implemente l'algorithme historique du Dispositif d'Accord Automatique decrit
 * dans "Synthese - Dispositif d'accord automatique ICRH TEXTOR" (section 5.2,
 * eq. 1-2) et dans les papiers Durodie 1992 (Design / First Results).
 *
 * DIFFERENCE MAJEURE PAR RAPPORT A LA VERSION PRECEDENTE :
 *   - Le panneau fournit DIRECTEMENT (VA - V+) et (VG - V+) sur leurs propres
 *     BNC : on n'a donc plus besoin de lire V1, V2 bruts et de soustraire V+
 *     en logiciel, on lit directement les differences deja calculees par le
 *     hardware. Cela suppose VA <-> V1 (distance l1) et VG <-> V2 (distance
 *     l2) -- A CONFIRMER (voir TODO ci-dessous).
 *
 * ⚠️ TODO CALIBRATION (inchange par rapport a avant) :
 *      - facteurs d'echelle ADC -> volts reels des sondes
 *      - gain k_v (papier: 0.2 (m/s)/kV pour sondes reelles, a reetalonner)
 *      - interface DAC GP8403 -> Copley 306 (polarite/gain mm-volt)
 *      - lecture des fins de course (endswitches)
 *
 * ⚠️ TODO A CONFIRMER AVEC TOI :
 *      1) VA correspond-il a la sonde a l1=1.35m et VG a l2=1.85m, ou
 *         l'inverse ? INCONNU pour l'instant -- voir le flag
 *         SWAP_VA_VG ci-dessous et la procedure empirique associee.
 * ============================================================================
 */

#include <math.h>
#include "DFRobot_GP8403.h"

// ---------------------------------------------------------------------------
// 0) MAPPING VA/VG <-> l1/l2 -- A DETERMINER EMPIRIQUEMENT (voir procedure)
// ---------------------------------------------------------------------------
// On ne sait pas encore si VA correspond a la sonde a l1 (et VG a
// l2), ou l'inverse. Mettre SWAP_VA_VG a true inverse l'association.
//
// PROCEDURE POUR LA DETERMINER SUR BANC (systeme hors tension RF, ou a
// tres faible puissance) :
//   1) Deplacer manuellement (ou par commande directe, boucle ouverte)
//      UNIQUEMENT Ca sur une petite plage connue, en gardant Cg fixe.
//   2) Observer via le port serie (println eps_a, eps_g) laquelle des
//      deux grandeurs eps_a/eps_g varie le plus fortement / de facon
//      coherente avec ce mouvement de Ca.
//   3) Si c'est eps_g qui bouge le plus alors qu'on deplace Ca, c'est que
//      le mapping est invers e -> mettre SWAP_VA_VG = true.
//   4) Repeter la meme verification en bougeant Cg seul, pour confirmer
//      la coherence dans les deux sens.
//   (Alternative plus directe si tu as le schema electrique du panneau :
//    remonter le cablage interne VA/VG jusqu'aux sondes physiques V1/V2
//    et leurs distances l1/l2 -- plus fiable que le test empirique.)
const bool SWAP_VA_VG = false;  // <-- ajuster ici une fois determine

// ---------------------------------------------------------------------------
// 1) Parametres RF (32.5 MHz, cf Table 1 des papiers)
// ---------------------------------------------------------------------------
const double FREQ_HZ   = 32.5e6;
const double C_LIGHT   = 299792458.0;
const double L1_M      = 1.35;   // distance sonde associee a VA (si SWAP_VA_VG=false)
const double L2_M      = 1.85;   // distance sonde associee a VG (si SWAP_VA_VG=false)
const double BETA      = 2.0 * PI * FREQ_HZ / C_LIGHT;

// Coefficients precalcules (constants car f, l1, l2 fixes)
double sin2bl1, cos2bl1, sin2bl2, cos2bl2;

// ---------------------------------------------------------------------------
// 2) Entrees analogiques -- CORRESPONDANCE AVEC LE PANNEAU REEL
// ---------------------------------------------------------------------------
//   Panneau       ->  Usage logiciel               -> Pin Arduino
//   V+             ->  Vplus (reference incidente)  -> A0
//   VA - V+        ->  eps_a_raw    -> A1
//   VG - V+        ->  eps_g_raw    -> A2
//   VA, VG (bruts) ->  non utilises par l'algorithme -> non cables (optionnel)
const int PIN_VPLUS       = A0;
const int PIN_VA_MINUS_VP = A1;   // = VA - V+, fourni directement par le hardware
const int PIN_VG_MINUS_VP = A2;   // = VG - V+, fourni directement par le hardware

// TODO CALIBRATION : facteurs [V reel / V ADC] a determiner par mesure
const double VPLUS_SCALE       = 1.0;
const double VA_MINUS_VP_SCALE = 1.0;
const double VG_MINUS_VP_SCALE = 1.0;
const double ADC_REF_V         = 5.0;     // tension de reference ADC Arduino
const double ADC_MAX           = 1023.0;  // 10 bits (Uno/Nano). Adapter si 12 bits.

// ---------------------------------------------------------------------------
// 3) Parametres de dynamique (papier "Design", section 4 - fideles)
// ---------------------------------------------------------------------------
const double V_MAX = 0.25;        // m/s, vitesse max des condensateurs
const double A_MAX = 50.0;        // m/s^2
const double K_A   = 50.0 / 0.05; // s^-1  (=1000)

// TODO CALIBRATION : gain eps -> vitesse. Le papier donne 0.2 (m/s)/kV pour
// les sondes reelles ; re-etalonner selon les echelles ci-dessus.
const double K_V = 2.0;

// Plage utile des condensateurs (papier "Design": 40-205 pF -> ~18-50mm)
const double X_MIN_MM = 18.0;
const double X_MAX_MM = 50.0;
const double X0_MM    = 35.0; // position de depart ("etat neutre")

// ---------------------------------------------------------------------------
// 4) Interface moteurs : DAC GP8403 (DFR0971, double, I2C) vers les
//    entrees POSITION des amplis Copley 306 (mode position) -- sorties
//    CA, CG du panneau.
// ---------------------------------------------------------------------------
#define ADRESSE_I2C_DAC 0x5F
DFRobot_GP8403 dac(&Wire, ADRESSE_I2C_DAC);

const int CANAL_CA = 0;
const int CANAL_CG = 1;

// Fins de course (a cabler en pull-up, LOW = fin de course atteinte)
const int PIN_ENDSW_CA_MIN = 2;
const int PIN_ENDSW_CA_MAX = 3;
const int PIN_ENDSW_CG_MIN = 4;
const int PIN_ENDSW_CG_MAX = 5;

// TODO CALIBRATION : relation position <-> tension DAC, mesuree sur CHAQUE
// canal separement (Ca et Cg peuvent avoir des gains differents) :
//   x_mm = m * V_DAC + c
const double DAC_VREF_V = 10.0;   // tension de reference du GP8403
bool CAL_DONE = false;
double M_CAL_A = 0.0, C_CAL_A = 0.0;
double M_CAL_G = 0.0, C_CAL_G = 0.0;

// Pile soustractive (meme principe que le script Python LabJack) pour
// atteindre les tensions negatives attendues par le Copley malgre un DAC
// qui ne sort que du positif.
const double OFFSET_PILE_V = 3.0; // V, tension de la pile

// ---------------------------------------------------------------------------
// Etat interne (vitesses actuelles, pour la limitation d'acceleration)
// ---------------------------------------------------------------------------
double v_a = 0.0, v_g = 0.0;
double pos_cmd_a_mm = X0_MM, pos_cmd_g_mm = X0_MM;
unsigned long t_prev_us = 0;

// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);

  sin2bl1 = sin(2.0 * BETA * L1_M);
  cos2bl1 = cos(2.0 * BETA * L1_M);
  sin2bl2 = sin(2.0 * BETA * L2_M);
  cos2bl2 = cos(2.0 * BETA * L2_M);

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

  t_prev_us = micros();
}

// ---------------------------------------------------------------------------
double readProbeVolts(int pin, double scale) {
  int raw = analogRead(pin);
  double v_adc = (raw / ADC_MAX) * ADC_REF_V;
  return v_adc * scale;
}

// ---------------------------------------------------------------------------
void writeDAC(int canal, double volts) {
  volts = constrain(volts, 0.0, DAC_VREF_V);
  dac.setDACOutVoltage((int)(volts * 1000.0), canal);
}

// ---------------------------------------------------------------------------
double vReelVersDac(double v_reel) {
  double v_dac = v_reel + OFFSET_PILE_V;
  if (v_dac < 0.0 || v_dac > DAC_VREF_V) {
    Serial.print("ATTENTION: v_reel=");
    Serial.print(v_reel, 3);
    Serial.println(" V hors plage atteignable, clippee.");
    v_dac = constrain(v_dac, 0.0, DAC_VREF_V);
  }
  return v_dac;
}

// ---------------------------------------------------------------------------
void outputPosition(double pos_mm, int canal, double m_cal, double c_cal) {
  double v_reel;
  if (CAL_DONE) {
    v_reel = (pos_mm - c_cal) / m_cal;
  } else {
    double frac = (pos_mm - X_MIN_MM) / (X_MAX_MM - X_MIN_MM);
    frac = constrain(frac, 0.0, 1.0);
    v_reel = frac * DAC_VREF_V;
  }
  double v_dac = vReelVersDac(v_reel);
  writeDAC(canal, v_dac);
}

// ---------------------------------------------------------------------------
void loop() {
  unsigned long t_now_us = micros();
  double dt = (t_now_us - t_prev_us) * 1e-6;
  t_prev_us = t_now_us;
  if (dt <= 0.0 || dt > 0.1) return;

  // --- Lecture des signaux disponibles sur le panneau ---
  double Vplus       = readProbeVolts(PIN_VPLUS,       VPLUS_SCALE);
  double VA_minus_Vp = readProbeVolts(PIN_VA_MINUS_VP, VA_MINUS_VP_SCALE);
  double VG_minus_Vp = readProbeVolts(PIN_VG_MINUS_VP, VG_MINUS_VP_SCALE);

  // --- Signaux d'erreur lineaires (eq. 1 et 2 de la synthese), a partir
  //     des differences DEJA calculees par le hardware du panneau.
  //     Le mapping VA/VG <-> l1/l2 etant incertain, on applique le flag
  //     SWAP_VA_VG defini plus haut. ---
  double sVA = SWAP_VA_VG ? VG_minus_Vp : VA_minus_Vp;  // associe a l1
  double sVG = SWAP_VA_VG ? VA_minus_Vp : VG_minus_Vp;  // associe a l2

  double eps_a = sVA * sin2bl2 - sVG * sin2bl1;
  double eps_g = sVA * cos2bl2 - sVG * cos2bl1;

  // --- Modulation de vitesse par |rho| : DESACTIVEE, pas de sonde V-
  //     disponible sur ce panneau. Vitesse max constante en attendant. ---
  double v_max_i = V_MAX;

  // --- Vitesses demandees, saturees ---
  double v_dem_a = constrain(K_V * eps_a, -v_max_i, v_max_i);
  double v_dem_g = constrain(K_V * eps_g, -v_max_i, v_max_i);

  // --- Fins de course : on interdit le mouvement dans le sens interdit ---
  if ((digitalRead(PIN_ENDSW_CA_MIN) == LOW || pos_cmd_a_mm <= X_MIN_MM) && v_dem_a < 0) v_dem_a = 0.0;
  if ((digitalRead(PIN_ENDSW_CA_MAX) == LOW || pos_cmd_a_mm >= X_MAX_MM) && v_dem_a > 0) v_dem_a = 0.0;
  if ((digitalRead(PIN_ENDSW_CG_MIN) == LOW || pos_cmd_g_mm <= X_MIN_MM) && v_dem_g < 0) v_dem_g = 0.0;
  if ((digitalRead(PIN_ENDSW_CG_MAX) == LOW || pos_cmd_g_mm >= X_MAX_MM) && v_dem_g > 0) v_dem_g = 0.0;

  // --- Limitation d'acceleration ---
  double acc_a = constrain(K_A * (v_dem_a - v_a), -A_MAX, A_MAX);
  double acc_g = constrain(K_A * (v_dem_g - v_g), -A_MAX, A_MAX);
  v_a += acc_a * dt;
  v_g += acc_g * dt;

  // --- Integration : vitesse virtuelle -> consigne de position [mm] ---
  pos_cmd_a_mm = constrain(pos_cmd_a_mm + v_a * dt * 1000.0, X_MIN_MM, X_MAX_MM);
  pos_cmd_g_mm = constrain(pos_cmd_g_mm + v_g * dt * 1000.0, X_MIN_MM, X_MAX_MM);

  // --- Sortie vers les amplis (DAC GP8403 -> BNC CA, CG du panneau) ---
  outputPosition(pos_cmd_a_mm, CANAL_CA, M_CAL_A, C_CAL_A);
  outputPosition(pos_cmd_g_mm, CANAL_CG, M_CAL_G, C_CAL_G);

  // --- Debug serie ---
  static unsigned long t_last_print = 0;
  if (millis() - t_last_print > 100) {
    t_last_print = millis();
    Serial.print("eps_a="); Serial.print(eps_a, 4);
    Serial.print(" eps_g="); Serial.print(eps_g, 4);
    Serial.print(" x_a_mm="); Serial.print(pos_cmd_a_mm, 3);
    Serial.print(" x_g_mm="); Serial.println(pos_cmd_g_mm, 3);
  }
}
