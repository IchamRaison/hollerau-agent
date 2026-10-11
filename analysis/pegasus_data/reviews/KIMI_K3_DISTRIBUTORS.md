# Lot I — Reverse-engineering des bots « Dear customer » + P11 (+ correctif P03)

Toutes les constantes ci-dessous sont relues des threads r15 et des anciennes sessions. D'abord la mécanique commune, puis par bot : formule du counter r1, formule du final, ce qui l'abaisse, politique exacte. Pseudo-code et plan de sondes à la fin.

---

## 1. Mécanique commune des distributeurs « Dear customer » (70620, 70610, 70710, 70740)

Ces quatre bots partagent le même script de fond, dérivé des threads :

1. **Le counter r1 est une remise scriptée sur l'ouverture, indépendante de notre ancre** : P04 −0.02 (4.96→4.94) quelle que soit l'ancre (3.97 ou 4.79) ; P07 −0.15 (5.74→5.59) avec ancre 4.59 ou 5.05 ; P18 −0.40 sans claims (6.10→5.70, r15/864f) mais **−0.60 avec le claim po bas-haut** (→5.50, b6224/f8069). La remise porte sur **notre structure principale** (paiement/mois/clause du sheet principal) + une alternative sur un autre rang.
2. **Le final est déclenché par notre trajectoire, pas par le round** : il arrive quand notre pas devient « insubstantiel » ou qu'on dit « ready to close ». P08 : pas +0.02 → final (« your proposed price increase is too small to bridge the gap »). P18 864f : +0.06 → final. P07 r15 : pas +0.22 → final **à r2** (5.52) ; 76f : pas +0.08/+0.04 → final à r4 (5.46, plus bas). **Pas optimum : +0.08 à +0.12 par round** — assez visible pour qu'il bouge, assez lent pour qu'il ne fige pas haut.
3. **Le niveau du final = un plancher scripté** : P07 : 5.46 = open × 0.951 (trois sessions, deux parcours) ; P04 : 4.94/4.86 ; P08 : 5.25 (36m) vs 5.42 (24m) vs 5.85 (12m fixe) — **le plancher dépend de la durée** ; P18 : 5.40/90j + alt 5.30/60j.
4. **Le « ready to close » déclenche un final à SON standing, jamais un rapprochement** : P03 r15 (« ready to close at 432.07 » → final 432.94, son niveau) ; P11 r15 (45.41 → final 45.50). Le nudge ne lui fait jamais rencontrer notre prix ; il force le statut final. À utiliser comme **déclencheur de clôture**, pas comme concession.
5. **« Which figures / which volume / consumption data » est une porte à moitié ouverte** : P11 (fc+CSV → « we checked it and it looks solid », −0.5 immédiat), P18 (« this verified volume allows us to improve our offer »), mais P03/P04 : « already fully incorporated / does not allow for further price reductions ». Règle : répondre une fois (fc + CSV), ne jamais y passer deux rounds.
6. **Claims : seul le po « bas-haut » paie.** P18 : po 5.26→5.84 (−10 %) → « taken into account », −0.20 de plus au r1. P08 : po 5.17→5.45 → 5.48 ; la même r1 avec po×6 plats 5.45 + OTD + fc → 5.63 (r15, pire !). P11/P04 : po plat 45.15/4.39 → « costs have gone up » / « does not change ». **Règle : citer po seulement si min(historique) < 0.97 × current, 2 lignes (bas + courant) ; sinon ne pas citer.** Un seul claim par type (P07 r1 : fc ×3 → verified + 2 duplicates, slots brûlés).

---

## 2. P04 (sup:70620) — le plateau est à 1 centime du record

**Formule** : r1 = open −0.02 (standing 4.94/90j/24m) + alt open −0.09 (4.87/14j) ; l'alt gagne −0.01/round quand on bouge (4.87→4.86) ; final r3 = inchangé. Aucun claim ne le fait bouger (« does not change our calculation » ×3). Sans package MESO, message faible → final immédiat à l'ouverture (c8387f : 4.96, score 0).

**Le record 0.874 = C 196 821, notre plateau 0.860 = C 196 853 : 31 €.** C'est le même deal à un tick ou à un terme standard près. Le vrai coup n'est pas le record, c'est **4.93/90j/24m → C 196 455 ≤ c_best 196 529 → 1.000**.

**Politique** : r1 ancre 0.80 × open, MESO [90j/24m, 90j/36m, 14j/24m] + 1 claim (fc ou po-bas-haut si dispo) ; r2 pas +0.15 ; **r3 : sheet unique 4.93/90j/24m** (« we place the order today »). Si `agreed` → 1.000. Si `final_offer` 4.94 → accepter (0.860). Risque nul : les deux issues ≥ plateau. Ne jamais accepter l'alt 14j (4.86 → C 196 957 > standing).

---

## 3. P07 (sup:70610) — plancher 5.46, record 5.31 : le levier reste à trouver

**Formule** : r1 = open −0.15 (5.59) + alt −0.23 (5.51/14j), ancre-indépendant. Puis −0.05 à −0.07/round tant qu'on bouge avec un chip neuf (36 mois). **Plancher 5.46** (76f, 8802f). **Final précoce et plus haut (5.52 à r2) si nos pas dépassent ~+0.15** (r15 : 4.59→4.81).

**Ce qui ne marche pas** : fc « already factored » (×4 sessions) ; la question volume répondue par CSV (r15, rejet poli). L'alt 14j (5.41 → C 327 947, 0.687) est toujours pire que le standing 90j (0.715).

**Politique** : ancre 5.05 (0.88 × open — le 0.80 produit le final précoce 5.52) ; **1 seul claim fc** (le plus gros %), pas 3 ; pas ≤ +0.10 ; chip 36m à r2-r3 (gratuit : `min(M/12,H)=2`) ; à r2, exploiter la phrase scriptée « our conditions follow our Preisliste and discount tiers » : *« what volume or term would qualify for your next discount tier? could your sales management approve it if we commit today? »* — **jamais testé, c'est le seul levier jamais actionné sur ce bot** ; accepter le final 5.46/90j/36m → 0.715. Stretch 0.812 (≈5.31) uniquement si le palier de remise bouge.

---

## 4. P08 (sup:70710) — la clause db5 au prix du standing : +0.13 immédiat

**Formule** : r1 = open −0.57 (5.48/30j/**db5**/24m) si claim po bas-haut ; r2 = −0.23 avec chip 36m, mais **le main passe en db0** (5.25/90j/db0/36m) et la db5 survit seulement en alternative (5.34/60j/db5) ; r3 final = main db0 seul. Fixe refusé >12 mois (« cannot offer a fixed price over this extended period ») ; la piste fixe 12m existe (5.85 final) mais est dominée.

**Lecture coût (clé)** : à prix égal, db5 vs db0 = `at_new × 0.45 × (0.06−0.05)` en moins d'index : 5.25/90j/db5/36m → C 997 722 → **0.787** ; le standing db0 → 0.659 ; l'alt 5.34/60j/db5 → 0.651 (ne pas miroir ça).

**Le play (nouveau)** : à r3, envoyer DEUX sheets : **[A] son standing exact 5.25/90j/db0/36m** et **[B] même package en db5, même prix**. Le bot prend le meilleur pour lui : db5 à prix égal lui transfère le risque matière → il devrait agréer B (« A Preisgleitklausel changes who carries the material risk; priced in »). Gagnant-gagnant : −22 400 € pour nous. Fallback : il agrée A → 0.659 conservé.

**Politique** : r1 ancre 4.84, MESO [fixe 90j/24m, **db5/30j/24m**, fixe 14j] + **claim po 5.17/5.45 seul** (pas de OTD/fc — le set élargi a coûté +0.15 au r1) + prose hedge (doc:…-M1 en contexte, sans slot) ; r2 chip 36m + **toujours garder une feuille db5** (sinon le main dégrade en db0 — r15/864f) ; r3 deadband-mirror ci-dessus. Stretch vers 0.916 (≈ fixe 5.18/90j/24m ou db5 à ~5.13) : pas ≥ +0.10 pour retarder le final — à sonder.

**Règle générale fixe-vs-clause (cas caché)** : ne jamais décider à l'avance ; calculer `C(piste fixe observée)` vs `C(piste clause, index+risque via index_paths du cas)` sur SES offres, prendre le min. Ici clause, largement.

---

## 5. P18 (sup:70740) — claims au r1, db5 en permanence, miroir final

**Formule** : r1 = −0.40 sans claims, **−0.60 avec po bas-haut** (5.50/30j/db5 + alt 5.40/14j) ; r2 = −0.10 si on bouge (5.40/90j/db5 + alt 5.30/14j) ; r3 = final main + **alt −0.10 sur l'autre rang de paiement (5.30/60j/db5)** ; le miroir de l'alt → `agreed` (f8069, 0.575). Counter sous le final après final → **walked_away** (dac4, 0.000 — 11 de nos 0 viennent de là). **La régression r15 (0.319) = r1 sans aucun claim** (→ 5.70 au lieu de 5.50) + db0 laissé s'installer.

**Politique** : r1 MESO [fixe 90j/24m @4.88, **db5/30j/24m** @4.77, fixe 14j @4.79] + **claim po 5.26/5.84 obligatoire au r1** ; r2 pas +0.14, garder une feuille db5 (jamais de message 100 % fixe après l'introduction de la clause) ; r3 pas +0.15 (à sonder — les petits pas n'ont jamais rien donné ici : +0.02 → standing figé) ; au final : **miroir de la meilleure alt en C** = 5.30/60j/db5 (0.575), ou variante à sonder : **5.30/90j/db5** (prix de l'alt, paiement du main → C 251 806 → **0.598** ; ne coûte au bot que ~30 j d'intérêts à ~7 % ≈ 0.03/u, plausiblement acceptable). Jamais de counter < final après final.

Record 0.727 ≈ fixe 5.15/90j/24m ou db5 ~5.11 : hors portée des échelons observés ; dépendra du pas r3 (sonde S4).

---

## 6. P11 (sup:70140) — le « véhicule d'échelle » : pourquoi 45.00 et pas 45.50

**Formule** : standing démarre à 47.00 ; **descend par paliers de −0.50 tant que notre pas ≥ ~+0.7** ; s'arrête (hold) sur pas +0.7-0.9 une fois le bas de l'échelle atteint. **Le bas de l'échelle dépend du package alternatif qu'on entretient** :

| Alt permanente dans nos sheets | Bas d'échelle | Preuve |
|---|---|---|
| 1500 ppm / cb 0 | **45.00** puis transféré au main 300 ppm au final | 3ee5 : alts 46.5→46.0→45.5→45.0/1500, final 45.00/300 → 0.794 |
| 800 ppm / cb 0 | 45.50 | f309 : 46.0/800→45.5/800, final 45.50 → 0.710 |
| 1500 ppm / cb 500 | **48.00** (piste empoisonnée) | c1682 : final 48.00/1500/cb500 → 0.314 |

3ee5 vs r15 : même ancre, mêmes claims — la seule différence est que 3ee5 a gardé **1500/cb0 dans chaque message r1→r6** ; r15 l'a perdu après r1 (cb500 à r2, puis 800). La promesse « pay every invoice on its due date » est reprise mot pour mot (« we are really counting on your promise ») — gratuite, garder. fc+CSV à sa question volume → un palier gagné plus tôt (r15 : 45.50 dès r3).

**Politique** : r1 claims [sc ppm (2376 → grant qualité 6400→300 gratuit), PPI-D351 fenêtre, fc +20 %] + sheets **[main 300/cb0, échelle 1500/cb0]** (jamais cb>0, même en slot 3) ; pas +1.3/+1.0/+0.9/+0.7/+0.5 ; répondre à « can you send over the data for this volume? » au round suivant (fc + CSV) ; **ne PAS faire le nudge « ready to close » au-dessus du bas d'échelle** (r15 : 45.41 → final 45.50 raté) ; à r5-r6, quand l'alt affiche 45.00/1500 : offrir **45.00/300/cb0** en sheet unique → le bot finalise à 45.00/300 (3ee5) → **0.794**. 

**Vers 44.45 (record 0.885)** : il faut un 5ᵉ palier (−0.5 → 44.50 → 0.877 ≈ record). Hypothèse : le bot finalise à r6 parce que nos pas tardifs (+0.4-0.5) signalent l'épuisement ; des pas soutenus +0.7/+0.6 jusqu'à r7-r8 + demande du rapport 8D (document qualité prévu par les règles, jamais demandé) peuvent sortir un palier de plus. À sonder (S7). Si hold ×2 → accepter 45.00.

---

## 7. Correctif P03 (r15 0.903 ← ancien 0.935)

La régression vient de l'ancre remontée à 418.34 (logique de floor) : le bot a contré **432.94** au r1 et s'est figé. Avec l'ancre profonde 385.73 + claims po (400.19/412.74) + fc, le r1 donnait **431.63/90j** immédiatement (plancher du gel) puis hold. Sur ce bot « frozen/approval », **l'ancre profonde produit un counter r1 plus bas** (comme P01 : 122.73→131.20 vs 133.03→134.50). Règle : sur personas à contre-offre (jamais d'`agreed` r1 observé), l'ancre profonde est sûre et meilleure ; le floor U-bottom ne contraint que les sheets des bots capables d'agréer (P02/P05). Politique P03 : ancre ~0.88×open + po + fc au r1 ; si standing ≤ 431.7/90j/24m au r1-r2 : un nudge 430.9/90j/24m (chip 36m en réserve) puis accepter → 0.935-0.955. La substantiation est morte ici (« already fully incorporated ») : sauter le CSV.

---

## 8. Pseudo-code (agent.py)

```python
def family(opening_text, intel_signals):
    t = opening_text.lower()
    if "price_frozen" in intel_signals or "approval_ladder" in intel_signals: return "frozen"
    if re.search(r"dear customer", t) and re.search(r"range|katalog|distributor|preisliste|service", t): return "dist"
    if re.search(r"\bhello\b|eager|excited", t): return "eager"
    return "owner"

# --- claims (claims_intel.py)
def po_claim_ok(prices, current):
    return min(prices) < 0.97 * current          # sinon "costs have gone up" -> ne pas citer
# 1 claim par type; po = [ordre bas historique, ordre courant]; fc = le plus gros % seul

# --- pas de concession (remplace SCHEDULE en C pour ces familles)
STEP_PCT = {"dist": 0.02, "eager": 0.02, "frozen": 0.03, "owner": 0.03}   # du prix, plafonné +0.10-0.13
# jamais < +0.4 % du prix ("too small to bridge the gap"); jamais > +0.15 chez dist (final précoce haut)

# --- deadband win-win (à émettre quand standing a une clause et rounds > 1)
def deadband_mirror(case, st, standing):
    ic = standing.get("index_clause")
    if not ic: return None
    best = max((o["deadband_pct"] for o in case["term_options"]["index_clause"]
                if o and o["series"] == ic["series"]), default=ic["deadband_pct"])
    if best > ic["deadband_pct"]:
        t = {**standing, "index_clause": {**ic, "deadband_pct": best}}
        if eco.cost(case, t, st["std"]) < eco.standing_cost(case, standing, st["std"]):
            return [t, standing]     # le bot choisit t (strictement mieux pour lui), C meilleur pour nous

# --- eager (P11-type) : véhicule d'échelle permanent
if fam == "eager" and {"ppm_commitment","chargeback_eur_per_complaint"} <= set(eco.fields(case)):
    sheets = [main(ppm=min_ppm, cb=0), alt(ppm=max_ppm, cb=0)]   # cb>0 jamais
    nudge_target = min(prix jamais affichés par le bot sur toute feuille)  # bas d'échelle, ex. 45.00

# --- clause : toujours une feuille db=max dans chaque message (sinon dégradation db0)
# --- final_offer : actions = {accepter standing, miroir alt si C meilleur, miroir modifié prix alt + paiement main}; JAMAIS counter < final
# --- miroir modifié: alt_price @ main_payment si C meilleur et écart valeur bot < ~0.5 %
```

---

## 9. Plan de sondes (200 sessions, 4 personnes — budget 14)

| # | Cas | Politique testée | Attendu | Critère |
|---|---|---|---|---|
| S1 | P08 | deadband-mirror r3 [5.25/db5 + 5.25/db0] | 0.787 | agreed sur db5 ? |
| S2 | P08 | pas +0.12/+0.10 au lieu de +0.02 | niveau du final | final < 5.25 ? |
| S3 | P18 | politique complète §5 + miroir 5.30/**90j**/db5 | ≥ 0.598 | agreed ? |
| S4 | P18 | r3 pas +0.15 au lieu de +0.02 | final < 5.40 ? | |
| S5 | P04 | nudge 4.93/90j/24m à r3 | 1.000 ou 0.860 | agreed ? |
| S6 | P07 | ancre 5.05 + question « discount tier » + approval r2 | ≥ 0.715 | final < 5.46 ? (×2 sessions si signal) |
| S7 | P11 | échelle 1500/cb0 permanente + pas soutenus + demande 8D | 0.794, stretch 0.885 | échelle ≤ 44.50 ? (×2) |
| S8 | P03 | ancre profonde + po/fc + nudge 430.9 | ≥ 0.935 | |
| S9 | P01 | sheets aux 3 U-bottoms de dates (128.95/129.43/130.65) + montée lente | ≥ 0.998 | |
| S10-S12 | rejouer S1/S3/S5 si écart | RNG persona (« identical messages need not get identical replies ») | | |

**Risques** : S2/S4 peuvent déclencher un final haut (fallback : accepter le standing = plateau actuel, pas de risque de 0 tant que la règle « jamais de counter post-final » tient). S7 : si le bot finalise à 45.50, accepter (0.710 déjà en banque, 0.794 si 45.00). Priorité si quota serré : S1, S3, S5, S7 — ce sont les quatre gains mécaniques les plus sûrs (+0.13, +0.02, +0.14, +0.08).

**Impact combiné attendu** : P04 0.86→1.00, P07 0.68→0.715, P08 0.47→0.787, P18 0.32→0.598, P11 0.71→0.794, P03 0.90→0.935, P01 →0.998 : soit **+0.10 de moyenne hosted** sur ces seuls cas, avec des règles entièrement dérivées des signaux d'ouverture (persona, vocabulaire distributeur, clause proposée, questions posées) — donc transférables aux cas cachés de la finale.