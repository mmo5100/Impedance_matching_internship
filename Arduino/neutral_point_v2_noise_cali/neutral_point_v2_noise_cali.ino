/*
 * BOUCLE FERMEE -- VERSION CONSOLIDEE v2, integrant :
 *
 *   1) MODE VITESSE (pas position) -- confirme par test au repos.
 *   2) ADC_REF_V mesure a 4.697V (pas 5.0V suppose).
 *   3) Gain/offset detecteurs VA et V+ (calibration_detecteurs.ino).
 *      VG reste non calibre (TODO).
 *   4) OFFSET_PILE_V mesure a 2.7V (pas 3.0V suppose).
 *   5) DAC_VREF_V=5.0V, aligne sur eOutputRange5V (registre reel du GP8403).
 *   6) K_V = 10.0 -- a valider empiriquement.
 *   7) NOUVEAU : calc_taux() -- compensation de stiction. Des que |eps|
 *      depasse EPS_DEADBAND, la commande de vitesse est forcee a au
 *      moins SEUIL_MECA_V (signe conserve), au lieu de laisser
 *      K_V*eps produire une commande sous le seuil mecanique mesure
 *      (~1V) qui n'a AUCUN effet physique. Ca decouple le seuil
 *      mecanique du deadband logiciel : EPS_DEADBAND peut maintenant
 *      etre choisi selon le bruit de mesure reel, pas selon la
 *      mecanique de l'actionneur.
 *
 * ⚠️ CE QUI RESTE NON CONFIRME / A FAIRE :
 *   - [RESOLU 25/08/2026] EPS_DEADBAND=0.13 valide via mesure_noise_floor.ino
 *     + filtre median-3 (sigma_filtre=0.0426/0.0336, 0 glitch residuel).
 *   - SEUIL_MECA_V=1.0 est la valeur mesuree empiriquement jusqu'ici --
 *     a reconfirmer si le comportement mecanique change (charge, usure...).
 *   - [RESOLU 25/08/2026] Coherence EPS_A_OFFSET/EPS_G_OFFSET vs gain/offset
 *     VA/V+ : confirmee EN CAUSE -- l'algo convergeait vers un faux zero
 *     (S11=-15dB au lieu de -48dB au vrai match Ca=31.39mm/Cg=31.13mm).
 *     Offsets recalibres par mesure directe au vrai match. A reverifier
 *     avec 1-2 points supplementaires pour confirmer que ca generalise
 *     dans le reste du domaine operationnel.
 *   - Working range non borne logiciellement -- rien n'empeche
 *     d'explorer toute la course si on part de tres loin.
 *   - VG non calibre en gain/offset (TODO) -- possible cause residuelle
 *     de l'ecart corrige ci-dessus (l'ecart etait plus marque sur eps_g).
 *     Calibrer VG en gain/offset donnerait probablement une correction
 *     plus robuste dans tout le domaine, plutot qu'un simple recalage
 *     ponctuel des offsets globaux.
 *   - Critere de convergence encore axe par axe (eps_a et eps_g testes
 *     independamment), pas sur l'erreur globale eps_a^2+eps_g^2. Un axe
 *     peut donc s'arreter pendant que l'autre bouge encore. Voir bloc
 *     CRITERE_COMBINE plus bas si tu veux basculer sur un critere unique.
 *
 * v3 -- AJOUT : filtre median-3 sur eps_a/eps_g avant calc_taux().
 * Mesures de bruit (mesure_noise_floor.ino) : ~1.3-3.2% des
 * echantillons sont des glitches isoles (valeurs 10-25x le bruit
 * normal, en rafales de quelques echantillons separees de plusieurs
 * secondes de calme -- cause exacte non identifiee, probablement un
 * evenement externe periodique plutot qu'un probleme de settling
 * ADC). Le filtre median-3 les elimine sans lisser excessivement le
 * signal (contrairement a une moyenne glissante). σ mesure hors
 * glitches : ~0.05-0.06 sur eps_a/eps_g -- c'est cette valeur qui doit
 * guider EPS_DEADBAND (3-5σ, donc ~0.15-0.30), PAS la valeur gonflee
 * par les glitches bruts.
 *
 * ⚠️ Tester a puissance RF REDUITE (10dBm).
 */

#include <math.h>
#include "DFRobot_GP8403.h"

// ---------------------------------------------------------------------------
const bool SWAP_VA_VG = false;

// --- Offsets de calibration eps_a/eps_g. RECALIBRES le 25/08/2026 a
// partir d'une mesure directe au vrai point de match (Ca=31.39mm,
// Cg=31.13mm, verifie S11=-48dB au VNA). Mesure statique (sans DAC
// actif, via mesure_noise_floor.ino) : eps_a_filtre=-0.05997,
// eps_g_filtre=-0.12466 a ce point -- ces valeurs sont ajoutees aux
// anciens offsets pour forcer eps_a=eps_g=0 exactement au vrai match :
//   ancien EPS_A_OFFSET=-0.081059 + (-0.05997) = -0.14103
//   ancien EPS_G_OFFSET=-0.134046 + (-0.12466) = -0.25871
// Avant cette correction, l'algo convergeait vers un faux zero (S11
// mesure = -15dB au lieu de -48dB) -- l'ecart etait plus marque sur
// eps_g, cohérent avec VG non calibre en gain/offset (voir TODO plus
// bas). A reverifier avec 1-2 mesures supplementaires autour du match
// pour confirmer que la correction generalise (pas un artefact d'un
// seul point).
const double EPS_A_OFFSET = -0.14103;
const double EPS_G_OFFSET = -0.25871;

const double FREQ_HZ = 38e6;
const double C_LIGHT = 299792458.0;
const double L1_M    = 1.35;
const double L2_M    = 1.85;
const double BETA    = 2.0 * PI * FREQ_HZ / C_LIGHT;
double sin2bl1, cos2bl1, sin2bl2, cos2bl2;

const int PIN_VPLUS = A2;
const int PIN_VA    = A0;
const int PIN_VG    = A1;

const double ADC_REF_V = 4.697;   // mesure reelle (pas 5.0V suppose)
const double ADC_MAX   = 1023.0;

const double VA_GAIN_CORR      = 1.02846;
const double VA_OFFSET_CORR    = -0.01242;
const double VPLUS_GAIN_CORR   = 1.16427;
const double VPLUS_OFFSET_CORR = -0.81718;
const double VG_GAIN_CORR   = 1.0;   // TODO : non calibre
const double VG_OFFSET_CORR = 0.0;

// --- Deadband logiciel : critere de convergence, INDEPENDANT du seuil
// mecanique grace a calc_taux() ci-dessous. VALIDE empiriquement le
// 25/08/2026 via mesure_noise_floor.ino + filtre median-3 :
// sigma_filtre = 0.0426 (eps_a) / 0.0336 (eps_g), 0 glitch residuel
// sur 819 echantillons. EPS_DEADBAND = 3 x sigma_max (0.0426).
// Si des faux arrets/oscillations apparaissent en test reel, remonter
// vers 5 sigma (~0.21) ; sinon cette valeur peut etre affinee a la
// baisse avec plus de donnees.
const double EPS_DEADBAND = 0.13;

// --- Seuil mecanique mesure empiriquement (~1V pour declencher un
// mouvement reel du Copley en mode vitesse).
const double SEUIL_MECA_V = 1.0;

// --- Bascule sur critere de convergence combine (eps_a et eps_g
// evalues ensemble via erreur = eps_a^2+eps_g^2) plutot qu'axe par
// axe. false = comportement actuel (axe par axe). Mettre a true une
// fois que EPS_DEADBAND est valide.
const bool CRITERE_COMBINE = false;

const int PIN_POS_CA = A3;
//const int PIN_POS_CG = A4;

const double POS_OFFSET_V = 3.0;  // offset materiel ajoute avant l'ADC, a retirer en lecture

// ---------------------------------------------------------------------------
// Dynamique -- vitesse envoyee directement au DAC (mode vitesse confirme)
// ---------------------------------------------------------------------------
const double TAUX_MAX_V_S = 1.8;       // vitesse max envoyee au DAC, > seuil mesure (~1V)
const double ACC_MAX_V_S2 = 20.0;
const double K_A          = 20.0/0.05;
const double K_V          = 10;      // a valider empiriquement

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
// calc_taux() -- compensation de stiction.
// Sous EPS_DEADBAND : commande nulle (arret voulu).
// Au-dessus : commande forcee a au moins SEUIL_MECA_V en magnitude,
// signe conserve, pour garantir un effet mecanique reel a chaque
// correction, meme quand K_V*eps serait sous le seuil mecanique.
// ---------------------------------------------------------------------------
double calc_taux(double eps) {
  if (fabs(eps) < EPS_DEADBAND) return 0.0;
  double taux = K_V * eps;
  if (fabs(taux) < SEUIL_MECA_V) {
    taux = (taux >= 0.0) ? SEUIL_MECA_V : -SEUIL_MECA_V;
  }
  return constrain(taux, -TAUX_MAX_V_S, TAUX_MAX_V_S);
}

// ---------------------------------------------------------------------------
// Filtre median-3 -- elimine les pics isoles (glitches ~1-3% des
// echantillons, cause exacte non identifiee, voir note v3 en en-tete)
// sans lisser excessivement le signal comme le ferait une moyenne
// glissante.
// ---------------------------------------------------------------------------
double median3(double a, double b, double c) {
  if ((a <= b && b <= c) || (c <= b && b <= a)) return b;
  if ((b <= a && a <= c) || (c <= a && a <= b)) return a;
  return c;
}

double buf_a[3] = {0, 0, 0};
double buf_g[3] = {0, 0, 0};
int nb_echantillons = 0;  // warm-up : les 2 premiers tours n'ont pas assez d'historique

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
  Serial.println("calc_taux() actif -- compensation de stiction.");

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

  double eps_a_brut = (sVA * sin2bl2 - sVG * sin2bl1) - EPS_A_OFFSET;
  double eps_g_brut = (sVA * cos2bl2 - sVG * cos2bl1) - EPS_G_OFFSET;

  buf_a[0] = buf_a[1]; buf_a[1] = buf_a[2]; buf_a[2] = eps_a_brut;
  buf_g[0] = buf_g[1]; buf_g[1] = buf_g[2]; buf_g[2] = eps_g_brut;
  if (nb_echantillons < 3) nb_echantillons++;

  double eps_a = (nb_echantillons < 3) ? eps_a_brut : median3(buf_a[0], buf_a[1], buf_a[2]);
  double eps_g = (nb_echantillons < 3) ? eps_g_brut : median3(buf_g[0], buf_g[1], buf_g[2]);

  double taux_dem_a, taux_dem_g;

  if (CRITERE_COMBINE) {
    // Critere combine : les deux axes s'arretent ensemble seulement
    // quand l'erreur globale est sous le seuil.
    double erreur2 = eps_a * eps_a + eps_g * eps_g;
    bool converge = (erreur2 < EPS_DEADBAND * EPS_DEADBAND);
    taux_dem_a = converge ? 0.0 : calc_taux(eps_a);
    taux_dem_g = converge ? 0.0 : calc_taux(eps_g);
  } else {
    // Comportement actuel : chaque axe s'arrete independamment.
    taux_dem_a = calc_taux(eps_a);
    taux_dem_g = calc_taux(eps_g);
  }

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
