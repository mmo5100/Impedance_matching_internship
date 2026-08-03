/*
 * Mesure continue de VA, VG, V+ et calcul de eps_a, eps_g -- PAS de DAC,
 * PAS de commande de tension, juste lecture + calcul.
 *
 * Le sketch prend exactement N_ECHANTILLONS mesures, s'arrete tout seul,
 * affiche la MOYENNE de ces N_ECHANTILLONS mesures, puis ATTEND qu'on
 * envoie n'importe quoi dans le Serial Monitor (Entree suffit) pour
 * relancer un nouveau cycle de N_ECHANTILLONS mesures.
 *
 * Cablage / lecture des sondes : identique a neutral_point.ino.
 *   V+ -> A2   VA -> A0   VG -> A1
 */

#include <math.h>

// ---------------------------------------------------------------------------
// Mapping VA/VG <-> l1/l2 (identique a neutral_point.ino)
// ---------------------------------------------------------------------------
const bool SWAP_VA_VG = false;

// ---------------------------------------------------------------------------
// Parametres RF
// ---------------------------------------------------------------------------
const double FREQ_HZ = 28e6;
const double C_LIGHT = 299792458.0;
const double L1_M    = 1.35;
const double L2_M    = 1.85;
const double BETA    = 2.0 * PI * FREQ_HZ / C_LIGHT;
double sin2bl1, cos2bl1, sin2bl2, cos2bl2;

// ---------------------------------------------------------------------------
// Entrees analogiques (identique a neutral_point.ino)
// ---------------------------------------------------------------------------
const int PIN_VPLUS = A2;
const int PIN_VA    = A0;
const int PIN_VG    = A1;

const double VPLUS_SCALE = 1.0;
const double VA_SCALE    = 1.0;
const double VG_SCALE    = 1.0;
const double ADC_REF_V   = 5.0;
const double ADC_MAX     = 1023.0;

const unsigned long PERIODE_ECHANTILLON_MS = 20;  // frequence d'echantillonnage
const int N_ECHANTILLONS = 100;                   // nombre de mesures par cycle

// ---------------------------------------------------------------------------
// Etat du sketch
// ---------------------------------------------------------------------------
enum EtatMesure { EN_COURS, ARRETE };
EtatMesure etat = EN_COURS;

// Accumulateurs
double sumVA = 0.0, sumVG = 0.0, sumVplus = 0.0;
double sumEpsA = 0.0, sumEpsG = 0.0;
int nEch = 0;
unsigned long t_dernier_echantillon = 0;

// ---------------------------------------------------------------------------
void setup() {
  Serial.begin(115200);

  sin2bl1 = sin(2.0 * BETA * L1_M);
  cos2bl1 = cos(2.0 * BETA * L1_M);
  sin2bl2 = sin(2.0 * BETA * L2_M);
  cos2bl2 = cos(2.0 * BETA * L2_M);

  Serial.println(F("Mesure de VA, VG, V+ -- eps_a, eps_g"));
  Serial.print(F("Prise de "));
  Serial.print(N_ECHANTILLONS);
  Serial.println(F(" mesures en cours..."));
  Serial.println();

  reinitialiserAccumulateurs();
}

// ---------------------------------------------------------------------------
double readProbeVolts(int pin, double scale) {
  int raw = analogRead(pin);
  double v_adc = (raw / ADC_MAX) * ADC_REF_V;
  return v_adc * scale;
}

void reinitialiserAccumulateurs() {
  sumVA = 0.0; sumVG = 0.0; sumVplus = 0.0;
  sumEpsA = 0.0; sumEpsG = 0.0;
  nEch = 0;
}

void afficherMoyenne() {
  Serial.println();
  Serial.println(F("=== Moyenne sur les mesures prises ==="));
  Serial.print(F("Nombre d'echantillons: ")); Serial.println(nEch);
  if (nEch == 0) {
    Serial.println(F("(aucun echantillon, rien a moyenner)"));
  } else {
    Serial.print(F("VA_moy    = ")); Serial.print(sumVA    / nEch, 4); Serial.println(F(" V"));
    Serial.print(F("VG_moy    = ")); Serial.print(sumVG    / nEch, 4); Serial.println(F(" V"));
    Serial.print(F("Vplus_moy = ")); Serial.print(sumVplus / nEch, 4); Serial.println(F(" V"));
    Serial.print(F("eps_a_moy = ")); Serial.print(sumEpsA  / nEch, 4);
    Serial.print(F("   eps_g_moy = ")); Serial.println(sumEpsG / nEch, 4);
  }
  Serial.println(F("======================================="));
  Serial.println(F("Envoyer n'importe quoi (Entree) pour relancer un nouveau cycle de mesure."));
  Serial.println();
}

// ---------------------------------------------------------------------------
void loop() {
  if (etat == ARRETE) {
    // On attend qu'on nous demande de relancer un nouveau cycle
    if (Serial.available()) {
      while (Serial.available()) Serial.read();  // vide le buffer d'entree
      reinitialiserAccumulateurs();
      etat = EN_COURS;
      Serial.print(F("Nouveau cycle demarre -- prise de "));
      Serial.print(N_ECHANTILLONS);
      Serial.println(F(" mesures..."));
    }
    return;
  }

  // --- etat EN_COURS : on echantillonne jusqu'a atteindre N_ECHANTILLONS ---
  unsigned long t_now = millis();
  if (t_now - t_dernier_echantillon < PERIODE_ECHANTILLON_MS) return;
  t_dernier_echantillon = t_now;

  double Vplus = readProbeVolts(PIN_VPLUS, VPLUS_SCALE);
  double VA    = readProbeVolts(PIN_VA,    VA_SCALE);
  double VG    = readProbeVolts(PIN_VG,    VG_SCALE);

  double VA_minus_Vp = VA - Vplus;
  double VG_minus_Vp = VG - Vplus;

  double sVA = SWAP_VA_VG ? VG_minus_Vp : VA_minus_Vp;
  double sVG = SWAP_VA_VG ? VA_minus_Vp : VG_minus_Vp;

  double eps_a = sVA * sin2bl2 - sVG * sin2bl1;
  double eps_g = sVA * cos2bl2 - sVG * cos2bl1;

  sumVA    += VA;
  sumVG    += VG;
  sumVplus += Vplus;
  sumEpsA  += eps_a;
  sumEpsG  += eps_g;
  nEch++;

  Serial.print(F("[")); Serial.print(nEch); Serial.print(F("/")); Serial.print(N_ECHANTILLONS); Serial.print(F("] "));
  Serial.print(F("VA=")); Serial.print(VA, 4);
  Serial.print(F(" VG=")); Serial.print(VG, 4);
  Serial.print(F(" V+=")); Serial.print(Vplus, 4);
  Serial.print(F(" eps_a=")); Serial.print(eps_a, 4);
  Serial.print(F(" eps_g=")); Serial.println(eps_g, 4);

  if (nEch >= N_ECHANTILLONS) {
    afficherMoyenne();
    etat = ARRETE;
  }
}
