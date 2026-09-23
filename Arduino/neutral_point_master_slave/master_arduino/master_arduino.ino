/*
 * BOUCLE FERMEE -- TEST D'ISOLATION : algo simple confirme bon (sans
 * calc_taux, sans filtre median, anciens offsets/deadband/ADC_REF_V)
 * + AJOUT UNIQUE de la lecture I2C de pos_Cg avec correction du
 * diviseur resistif.
 *
 * Objectif : isoler si l'ajout du deuxieme Arduino (lecture I2C de
 * pos_Cg) degrade a lui seul le comportement de la boucle fermee,
 * independamment de tous les autres changements (calc_taux, filtre
 * median, EPS_DEADBAND=0.13, offsets recalibres, ADC_REF_V=4.697)
 * qui ont ete ajoutes ensemble dans la version v3 et qui matchait
 * moins bien.
 *
 * CE QUI VIENT DE LA VERSION SIMPLE CONFIRMEE BONNE (inchange) :
 *   - EPS_A_OFFSET/EPS_G_OFFSET (anciens : -0.081059/-0.134046)
 *   - ADC_REF_V = 5 (suppose, pas remesure)
 *   - VA_GAIN_CORR/VPLUS_GAIN_CORR (calibration_detecteurs.ino)
 *   - EPS_DEADBAND = 0.001
 *   - taux_dem calcule directement (constrain(K_V*eps,...)), SANS
 *     calc_taux()/compensation de stiction
 *   - Pas de filtre median
 *
 * CE QUI EST AJOUTE (nouveau, isole) :
 *   - Lecture de pos_Cg via I2C depuis le deuxieme Arduino esclave
 *     (adresse 0x08) -- voir esclave_pos_cg.ino
 *   - Correction du diviseur resistif 1/3 + offset +3V sur pos_ca ET
 *     pos_cg (V_reel = (V_ADC - POS_OFFSET_V) * RAPPORT_DIVISEUR_POS)
 *     -- concerne uniquement l'affichage/logging de position, n'entre
 *     PAS dans le calcul de eps_a/eps_g, donc ne devrait avoir aucun
 *     impact sur la qualite de convergence elle-meme.
 *
 * PROTOCOLE DE TEST :
 *   1) Flash ce fichier, reteste le matching dans les memes conditions
 *      que la version simple qui marchait bien.
 *   2) Si le match reste bon -> confirme que l'I2C seul n'etait pas la
 *      cause de la degradation observee sur v3. Le probleme vient donc
 *      d'ailleurs (calc_taux, filtre, ou plus probablement le
 *      changement combine de EPS_DEADBAND+offsets recalibres sans
 *      revalidation coherente).
 *   3) Si le match se degrade deja ici -> confirme que c'est bien
 *      l'ajout du deuxieme Arduino (bruit electrique couple, ou latence
 *      de Wire.requestFrom() perturbant dt) qui est en cause.
 *
 *  Tester a puissance RF REDUITE (10dBm).
 */

#include <math.h>
#include <Wire.h>
#include "DFRobot_GP8403.h"

// ---------------------------------------------------------------------------
const bool SWAP_VA_VG = false;

const double EPS_A_OFFSET = -0.081059;
const double EPS_G_OFFSET = -0.134046;

const double FREQ_HZ = 38e6;
const double C_LIGHT = 299792458.0;
const double L1_M    = 1.35;
const double L2_M    = 1.85;
const double BETA    = 2.0 * PI * FREQ_HZ / C_LIGHT;
double sin2bl1, cos2bl1, sin2bl2, cos2bl2;

const int PIN_VPLUS = A2;
const int PIN_VA    = A0;
const int PIN_VG    = A1;

const double ADC_REF_V = 5;
const double ADC_MAX   = 1023.0;

const double VA_GAIN_CORR      = 1.02846;
const double VA_OFFSET_CORR    = -0.01242;
const double VPLUS_GAIN_CORR   = 1.16427;
const double VPLUS_OFFSET_CORR = -0.81718;
const double VG_GAIN_CORR   = 1.0;   // TODO : non calibre
const double VG_OFFSET_CORR = 0.0;

const double EPS_DEADBAND = 0.001;  // a ajuster selon le bruit mesure

const int PIN_POS_CA = A3;

// --- Offset materiel reel = +3V, et rapport du diviseur resistif 1/3
// (V_ADC = V_reel/3 + POS_OFFSET_V) -- applique a pos_ca ET pos_cg,
// AJOUT par rapport a la version simple d'origine, mais n'affecte que
// l'affichage/logging de position, pas le calcul de eps.
// ---------------------------------------------------------------------------
const double POS_OFFSET_V = 3.0;
const double RAPPORT_DIVISEUR_POS = 6.0;

// --- NOUVEAU (isole) : lecture de pos_Cg via I2C (deuxieme Arduino
// esclave) ---
#define ADRESSE_I2C_ESCLAVE_POSCG 0x08

// TODO : mesurer separement l'ADC_REF_V du deuxieme Arduino.
const double ADC_REF_V_ARDUINO2 = 4.782;  // PLACEHOLDER, a calibrer

// ---------------------------------------------------------------------------
// Dynamique -- vitesse envoyee directement au DAC (mode vitesse confirme)
// ---------------------------------------------------------------------------
const double TAUX_MAX_V_S = 1.8;       // vitesse max envoyee au DAC, > seuil mesure (~1V)
const double ACC_MAX_V_S2 = 20.0;
const double K_A          = 20.0/0.05;
const double K_V          = 10;      // augmente vs 2.0 -- a valider empiriquement

// ---------------------------------------------------------------------------
#define ADRESSE_I2C_DAC 0x5F
DFRobot_GP8403 dac(&Wire, ADRESSE_I2C_DAC);

const int CANAL_CA = 0;
const int CANAL_CG = 1;

const int PIN_ENDSW_CA_MIN = 2;
const int PIN_ENDSW_CA_MAX = 3;
const int PIN_ENDSW_CG_MIN = 4;
const int PIN_ENDSW_CG_MAX = 5;

const double DAC_VREF_V    = 5.0;
const double OFFSET_PILE_V = 2.7;

// ---------------------------------------------------------------------------
double vel_a = 0.0, vel_g = 0.0;
unsigned long t_prev_us = 0;

// ---------------------------------------------------------------------------
void outputTensionReelle(double v_reel, int canal) {
  double v_dac = constrain(v_reel + OFFSET_PILE_V, 0.0, DAC_VREF_V);
  dac.setDACOutVoltage((int)(v_dac * 1000.0), canal);
}

// ---------------------------------------------------------------------------
// NOUVEAU (isole) -- lecture de pos_Cg via I2C depuis le deuxieme
// Arduino (esclave, voir esclave_pos_cg.ino). Renvoie NAN si la
// lecture echoue, pour ne pas faire planter la boucle principale.
// Applique la meme inversion du diviseur que pos_ca.
// ---------------------------------------------------------------------------
double lirePosCgViaI2C() {
  Wire.requestFrom(ADRESSE_I2C_ESCLAVE_POSCG, 2);
  if (Wire.available() >= 2) {
    int valeur_brute = (Wire.read() << 8) | Wire.read();
    double v_adc = (valeur_brute / ADC_MAX) * ADC_REF_V_ARDUINO2;
    return (v_adc - POS_OFFSET_V) * RAPPORT_DIVISEUR_POS;
  }
  return NAN;
}

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
  Serial.println("RAPPEL : tester a puissance RF REDUITE (10dBm).");
  Serial.println("MODE VITESSE -- v=0 => moteur immobile la ou il est.");
  Serial.println("TEST ISOLATION -- algo simple + ajout unique pos_Cg via I2C.");

  pinMode(PIN_ENDSW_CA_MIN, INPUT_PULLUP);
  pinMode(PIN_ENDSW_CA_MAX, INPUT_PULLUP);
  pinMode(PIN_ENDSW_CG_MIN, INPUT_PULLUP);
  pinMode(PIN_ENDSW_CG_MAX, INPUT_PULLUP);

  t_prev_us = micros();
}

// ---------------------------------------------------------------------------
void loop() {
  unsigned long t_now_us = micros();
  double dt = (t_now_us - t_prev_us) * 1e-6;
  t_prev_us = t_now_us;
  if (dt <= 0.0 || dt > 0.1) return;

  double Vplus = ((analogRead(PIN_VPLUS) / ADC_MAX) * ADC_REF_V) * VPLUS_GAIN_CORR + VPLUS_OFFSET_CORR;
  double VA    = ((analogRead(PIN_VA)    / ADC_MAX) * ADC_REF_V) * VA_GAIN_CORR    + VA_OFFSET_CORR;
  double VG    = ((analogRead(PIN_VG)    / ADC_MAX) * ADC_REF_V) * VG_GAIN_CORR    + VG_OFFSET_CORR;

  // MODIFIE -- inversion complete du diviseur (retrait offset PUIS
  // multiplication par RAPPORT_DIVISEUR_POS), pour affichage seulement.
  double v_adc_ca = (analogRead(PIN_POS_CA) / ADC_MAX) * ADC_REF_V;
  double pos_ca = (v_adc_ca - POS_OFFSET_V) * RAPPORT_DIVISEUR_POS;

  // NOUVEAU (isole) -- lecture via I2C au lieu du analogRead local
  // d'origine (qui etait de toute facon commente dans la version
  // simple, faute de broche libre).
  double pos_cg = lirePosCgViaI2C();

  double VA_minus_Vp = VA - Vplus;
  double VG_minus_Vp = VG - Vplus;
  double sVA = SWAP_VA_VG ? VG_minus_Vp : VA_minus_Vp;
  double sVG = SWAP_VA_VG ? VA_minus_Vp : VG_minus_Vp;

  // INCHANGE -- meme formule que la version simple confirmee bonne,
  // pas de filtre median.
  double eps_a = (sVA * sin2bl2 - sVG * sin2bl1) - EPS_A_OFFSET;
  double eps_g = (sVA * cos2bl2 - sVG * cos2bl1) - EPS_G_OFFSET;

  // INCHANGE -- pas de calc_taux()/compensation de stiction, comme
  // dans la version simple confirmee bonne.
  double taux_dem_a = (fabs(eps_a) < EPS_DEADBAND) ? 0.0 : constrain(K_V * eps_a, -TAUX_MAX_V_S, TAUX_MAX_V_S);
  double taux_dem_g = (fabs(eps_g) < EPS_DEADBAND) ? 0.0 : constrain(K_V * eps_g, -TAUX_MAX_V_S, TAUX_MAX_V_S);

  if (digitalRead(PIN_ENDSW_CA_MIN) == LOW && taux_dem_a < 0) taux_dem_a = 0.0;
  if (digitalRead(PIN_ENDSW_CA_MAX) == LOW && taux_dem_a > 0) taux_dem_a = 0.0;
  if (digitalRead(PIN_ENDSW_CG_MIN) == LOW && taux_dem_g < 0) taux_dem_g = 0.0;
  if (digitalRead(PIN_ENDSW_CG_MAX) == LOW && taux_dem_g > 0) taux_dem_g = 0.0;

  double acc_a = constrain(K_A * (taux_dem_a - vel_a), -ACC_MAX_V_S2, ACC_MAX_V_S2);
  double acc_g = constrain(K_A * (taux_dem_g - vel_g), -ACC_MAX_V_S2, ACC_MAX_V_S2);
  vel_a += acc_a * dt;
  vel_g += acc_g * dt;

  outputTensionReelle(vel_a, CANAL_CA);
  outputTensionReelle(vel_g, CANAL_CG);

  static unsigned long t_last_print = 0;
  if (millis() - t_last_print > 100) {
    t_last_print = millis();
    Serial.print("VA="); Serial.print(VA, 4);
    Serial.print(" VG="); Serial.print(VG, 4);
    Serial.print(" V+="); Serial.print(Vplus, 4);
    Serial.print(" pos_a="); Serial.print(pos_ca, 4);
    Serial.print(" pos_g="); Serial.print(pos_cg, 4);
    Serial.print(" eps_a="); Serial.print(eps_a, 4);
    Serial.print(" eps_g="); Serial.print(eps_g, 4);
    Serial.print(" erreur="); Serial.print(eps_a * eps_a + eps_g * eps_g, 5);
    Serial.print(" vel_a="); Serial.print(vel_a, 3);
    Serial.print(" vel_g="); Serial.println(vel_g, 3);
  }
}