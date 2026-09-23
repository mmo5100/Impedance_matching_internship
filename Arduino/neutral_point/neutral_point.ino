/*
 * BOUCLE FERMEE -- VERSION CONSOLIDEE, integrant toutes les corrections
 * confirmees experimentalement jusqu'ici :
 *
 *   1) MODE VITESSE (pas position) -- confirme par test au repos : a
 *      v_reel=0V le moteur s'arrete net la ou il se trouve, il ne
 *      retourne PAS a une position de reference. Une seule integration
 *      (eps -> vitesse), pas de position accumulee.
 *   2) ADC_REF_V mesure a 4.697V (pas 5.0V suppose).
 *   3) Gain/offset detecteurs VA et V+ (calibration_detecteurs.ino).
 *      VG reste non calibre (TODO).
 *   4) OFFSET_PILE_V mesure a 2.7V (pas 3.0V suppose).
 *   5) DAC_VREF_V=5.0V, aligne sur eOutputRange5V (registre reel du GP8403).
 *   6) K_V augmente a 10.0 (au lieu de 2.0) pour retrecir la zone de
 *      capture autour du match : avec le seuil de mouvement mesure a
 *      ~1V, K_V=2.0 impliquait que le systeme pouvait s'arreter des que
 *      |eps|<0.5 -- bien trop large. Avec K_V=10.0, le systeme continue
 *      de bouger jusqu'a |eps|<0.1 -- PAS ENCORE VALIDE EMPIRIQUEMENT,
 *      a ajuster selon les tests.
 *
 *  CE QUI RESTE NON CONFIRME / A FAIRE AVANT DE CONSIDERER CE CODE
 * COMME DEFINITIF :
 *   - La coherence entre EPS_A_OFFSET/EPS_G_OFFSET (calibres anterieurement)
 *     et les nouvelles corrections gain/offset VA/V+ n'a jamais ete
 *     verifiee explicitement -- si le systeme converge de facon repetable
 *     vers un point decale du vrai match connu (Ca=31.39mm, Cg=31.13mm),
 *     c'est le premier suspect a recalibrer.
 *   - Le "working range" (plage de fonctionnement) n'a pas ete restreint
 *     a une zone centrale ou le critere d'unicite du zero est garanti --
 *     actuellement aucune borne logicielle de position n'existe (mode
 *     vitesse), donc rien n'empeche le systeme d'explorer toute la
 *     course s'il part de tres loin. A surveiller lors des tests.
 *   - VG n'a pas de calibration gain/offset propre.
 *   - K_V=10.0 est une premiere estimation, pas une valeur validee.
 *
 *  Tester a puissance RF REDUITE (10dBm).
 */

#include <math.h>
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


const double EPS_DEADBAND = 0.001;  // à ajuster selon le bruit mesuré




const int PIN_POS_CA = A3;
//const int PIN_POS_CG = A4;

const double POS_OFFSET_V = 3.0;  // offset matériel ajouté avant l'ADC, à retirer en lecture

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


  // --- AJOUT DEBUG ---
  //Serial.print(canal == CANAL_CA ? "CA v_dac=" : "CG v_dac=");
  //Serial.println(v_dac, 3);
  // -------------------

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

  double pos_ca = ((analogRead(PIN_POS_CA) / ADC_MAX) * ADC_REF_V) - POS_OFFSET_V;
 // double pos_cg = ((analogRead(PIN_POS_CG) / ADC_MAX) * ADC_REF_V) - POS_OFFSET_V;

  double VA_minus_Vp = VA - Vplus;
  double VG_minus_Vp = VG - Vplus;
  double sVA = SWAP_VA_VG ? VG_minus_Vp : VA_minus_Vp;
  double sVG = SWAP_VA_VG ? VA_minus_Vp : VG_minus_Vp;

  double eps_a = (sVA * sin2bl2 - sVG * sin2bl1) - EPS_A_OFFSET;
  double eps_g = (sVA * cos2bl2 - sVG * cos2bl1) - EPS_G_OFFSET;

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
  //  Serial.print(" pos_g="); Serial.print(pos_cg, 4);
    Serial.print(" eps_a="); Serial.print(eps_a, 4);
    Serial.print(" eps_g="); Serial.print(eps_g, 4);
    Serial.print(" erreur="); Serial.print(eps_a * eps_a + eps_g * eps_g, 5);
    Serial.print(" vel_a="); Serial.print(vel_a, 3);
    Serial.print(" vel_g="); Serial.println(vel_g, 3);
  }
}
