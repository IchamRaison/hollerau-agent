# PEGASUS — Plan de bataille pour la Finale

Réponse structurée en 11 blocs. Convention : **[Mécanisme]** = règle générale (aucune donnée de cas codée en dur), **[SONDE n]** = hypothèse à vérifier en session de pratique, avec priorité. Tous les chiffres C sont recomputés à partir de vos replays et de `arena_kit/cost.py`.

---

## 0. Synthèse exécutive — ce qui rapporte, par ordre d'impact

| # | Mécanisme | Gain estimé (points de score moyen hosted) | Risque de 0 | Effort |
|---|---|---|---|---|
| M1 | Tout décider en **C_rel** (charge de relation incluse) : ancre, schedule, MESO, acceptation | P02 0.684→0.734 mécanique ; P01 re-stabilisé à ~0.99 ; supprime les 0.0 (344.2/14 = rel 143 k€) | faible (sol bien géré) | 2h |
| M5 | **Machine à statuts** : agreed→conversion de rang ; final→accepter/miroir, jamais de counter ; nudge −1 tick pendant `open` ; watchdog anti-timeout | élimine les 0.0 (P05, P10, P18) ; P04 0.860→1.0 possible ; P01 +0.002 | faible si règles strictes | 1h30 |
| M3 | **Répondre aux questions scriptées** (volume/« which figures »/forecasts) avec la bonne pièce au bon moment + pièce jointe CSV | P03 +0.02-0.03, P10 +0.02, P18 +0.05-0.15, P07 +0.03-0.05, P01 le dernier 0.3 € | ~0 | 1h30 |
| M8 | **RFQ ratchet** P05 : citations rivales fraîches chaque round, interdiction d'`agreed` précoce, clôture au plancher révélé | P05 0.734→0.81-0.97 | timeouts si watchdog absent | 1h30 |
| M4 | **Driver-window claims** : citer les propres indices du bot sur la fenêtre la plus favorable | P02/P03/P08/P18 : ramollissement du plancher de 0.3-1.5 € | nul si on ne cite que du favorable | 1h |
| M2 | Inférence à chaud du **taux de cash** (paires de ré-offres) → choix du rang de paiement | inclus dans M1 ; fiabilise la structure | faible (bornes + priors) | 1h |
| M6 | MESO 2.0 : variantes à C_rel égal, chacune ≥ son U-bottom ; variante « jackpot » | élimine le piège MESO (P02 r1), sonde de taux gratuite | faible | 30 min |
| M7 | Robustesse finale : watchdog 40 s, LLM hors chemin critique, schedule compressé, closing à cap−40 s, reprise sur crash | élimine les timeouts (2 zeros connus) | — | 1h30 |

Le reste est secondaire. Nos zéros et nos régressions viennent de M1/M5/M7, pas de la qualité des e-mails.

---

## 1. M1 — Tout décider en C_rel (le bug structurel central)

### Diagnostic

Sur les cas `stabilise`/`secure_supply`, le score facture la **charge de relation** (`cost.py` : `relationship_eur_per_point · soft(sustainable_margin − margin) · years`, marge calculée sur la *valeur cash* du deal pour le fournisseur). Or `agent.py` calcule le point de référence des concessions **sans** cette charge :

```python
offers = [eco.standing_cost(case, t, st["std"]) ...]   # plain C !
target = anchor + SCHEDULE[k] * max(c_s - anchor, 0)    # on converge vers le mauvais C
```

Conséquences observées dans vos propres résultats :

- P02 `d9b2cd2c` : deal 344.20/14/index → `relationship=143 194 €`, score **0.000**. Le bot a dit « agreed » à un prix très sous son coût complet — le script le permet, l'arène le facture.
- P01 `1122e2a1` : ancre 133.03/Apr/90 = « le fond de la MAUVAISE structure » (votre note) → deal 134.5/Apr/60, score 0.953 alors que 131.2/Apr/14 vaut 0.998.
- P01 `3a0b48ea` : 131.2/Apr/14, score 0.998 — la bonne structure (14 j) est connue, elle doit être choisie par le modèle, pas par accident.

### Règle générale

Sur `category_goal ∈ {stabilise, secure_supply}` avec `relationship_eur_per_point > 0` : **toutes** les grandeurs de décision (c_s, ancre, schedule, `best_at_price`, `closing`, `_accept_best`) utilisent `stdC = eco.with_relationship(std)` où `_floor` porte le modèle fournisseur (M2). La grille, les U-bottoms et les prix cibles sont calculés avec `stdC`.

```python
def stdC(case, st):
    b = case["buyer"]
    if b.get("category_goal") in REL_GOALS and st["std"].get("_floor"):
        return eco.with_relationship(st["std"])
    return st["std"]

# structure optimale : argmin_s C_rel(sheet(s, cheapest_price(s, stdC)))
def best_structure_rel(case, stdC):
    return min((eco.cost(case, eco.sheet(case, s, eco.cheapest_price(case, s, stdC, 0.01, hi)), stdC), s)
               for s in eco.grid(case))[1]
```

### Règle du rang de paiement (dérivée du t

## 1. M1 — Prix, concessions et acceptation en C_rel (charge de relation incluse)

**Module : `agent.py`, `economics.py`. Priorité P0.**

### Diagnostic

Sur `stabilise`/`secure_supply`, le score facture `relationship_eur_per_point · soft(sustainable_margin − margin) · years` (cost.py), la marge étant calculée sur la **valeur cash** du deal pour le fournisseur. Or notre moteur de concession travaille en C « nu » :

```python
offers = [eco.standing_cost(case, t, st["std"]) ...]        # C sans charge de relation
target = anchor + SCHEDULE[k] * max(c_s - anchor, 0)        # convergence vers le mauvais C
```

Preuves de la casse, dans nos propres sessions :
- P02 `d9b2cd2c` : deal 344.20/14j/index → `relationship=143 194 €`, score **0.000** (le bot a dit `agreed` à un prix très sous son coût complet — son script le permet, l'arène le facture).
- P02 `cd6c9472` : 345.15/14j → rel 133 838 €, score 0.011.
- P01 `1122e2a1` : ancre 133.03/Apr/90 = fond de la **mauvaise structure** → deal 134.5/Apr/60, score 0.953, alors que `3a0b48ea` (131.2/Apr/14) vaut 0.998 et que le fond du U en C_rel est à 14 jours.

### Règle générale

Toutes les grandeurs de décision utilisent `stdC` :

```python
REL_GOALS = {"stabilise", "secure_supply"}

def stdC(case, st):
    b = case["buyer"]
    if b.get("category_goal") in REL_GOALS and b.get("relationship_eur_per_point") and st["std"].get("_floor"):
        return eco.with_relationship(st["std"])   # _supplier = modèle fournisseur (M2)
    return st["std"]

# partout dans decide/_accept_best/closing/_anchor :
c_s      = min(eco.standing_cost(case, t, stdC) for _, t in offered(events) if eco.ok(case, t, st["std"]))
target   = anchor_C + SCHEDULE[k] * max(c_s - anchor_C, 0)     # SCHEDULE en C_rel
anchor_s = eco.best_at_price(case, expected_price, stdC, current)  # structure au prix attendu, en C_rel
```

### Structure optimale et rang de paiement

La règle du rang : le bot re-price ses propres termes à **son** taux `r̂_s` ; notre C facture le paiement à 8 % (buyer `interest_rate`). Donc :
- si `r̂_s < 8 %` → paiement **long** (90 j) : son surcoût prix < notre gain d'intérêt (P03 : −26 358 € de `payment_terms` à 90 j ; P02 : 90 j à valeur-parité = 360.89 bat 60 j à 358.95 de ~2 700 €) ;
- si `r̂_s > 8 %` → paiement **court** (14 j) : sa remise cash bat notre coût d'intérêt (P01 : fond du U à 130.65/Apr/14j vs ~133/Apr/90j).

```python
def best_structure_rel(case, stdC):
    """La structure dont le fond du U (en C_rel) est le plus bas."""
    best = None
    for s in eco.grid(case):
        p = eco.cheapest_price(case, s, stdC, 0.01, hi)   # fond du U de CETTE structure
        c = eco.cost(case, eco.sheet(case, s, p), stdC)
        if best is None or c < best[0]:
            best = (c, s, p)
    return best  # -> ex. P01: (~1 096 809, Apr/14j, 130.65)
```

### Ancre et schedule

- **Ancre = prix du fond du U de la meilleure structure** (ni au-dessus — P01 133.03 → settle 134.5 ; ni très en-dessous — les feuilles sont de toute façon re-floorées). `[SONDE P01]` : vérifier qu'une ancre floorée à 130.65/Apr/14 settle bien ~131.2 comme l'ancre profonde 122.73 l'a fait en `3a0b48ea`.
- **Schedule en C_rel** : `target = anchor_C + frac × (c_s_rel − anchor_C)`, monotone non décroissant (jamais de retraite), avec pas minimal visible en prix : ΔP ≥ 0,4 % du prix (le bot répond « you only moved by one cent » / « we hold our Angebot » si le pas est trop petit) :

```python
min_step_C = 0.004 * spend_estime
if target - st["last_target"] < min_step_C and c_s > target + eps:
    target = st["last_target"] + min_step_C
```

### Gain / risque

- P02 : 0.684 → 0.734 mécaniquement (rung 90 j au lieu de 60 j à valeur-parité), suppression définitive des 0.000 par prix sous coût.
- P01 : re-stabilisation ~0.99+ (la régression 0.953 vient de la structure Apr/90).
- Risque : modèle fournisseur faux (fc, taux) → bornes + ré-inférence M2 ; le floor `_floored` reste absolu (jamais de feuille sous le U-bottom), ce qui borne la perte même si le bot accepte.

---

## 2. M2 — Inférence à chaud du taux de cash et du coût complet

**Module : `economics.py` (nouveau `infer_rate`), `agent.py`. Priorité P0 (petit).**

### Taux de cash du fournisseur — règle générale

Le bot publie ses échelons de prix par rang de paiement **dans le même round** (offre principale + « Alternatively, with Zahlungsziel … days net: €… »). Deux échelons du même round donnent son taux directement, sans mélange avec ses concessions :

```python
def infer_rate(pairs):
    """pairs = [(price_1, days_1), (price_2, days_2)] issus de la MEME reponse."""
    rates = []
    for (p1, d1), (p2, d2) in combinations(pairs, 2):
        if d1 != d2:
            # valeur-parité : p1*(1 - r*d1/360) = p2*(1 - r*d2/360)
            r = (p2 - p1) / (p1*d1 - p2*d2) * 360
            if 0.03 <= r <= 0.15:
                rates.append(r)
    return median(rates) if rates else None
```

Preuves que ça marche (paires du même round, pas cross-round) :
- P02 `32b3b929` r1 : 373.88/90 vs « Alternatively … 14 days net: €368.68 » → r = 6.6 % ✓ (le taux calibré).
- P02 `f712b503` r4 : 372.23/90 vs 367.05/14 → 6.6 % ✓.
- P03 `f518d960` r1 : 431.63/90 vs 426.97/14 → 5.9 % (vrai 6.1 % — l'écart inclut un soupçon de concession commerciale ; médiane sur plusieurs paires et borne [3 %, 15 %] suffisent à trancher le rang : < 8 % → 90 j ✓).
- P01 `3a0b48ea` : 137.90/45j r1 puis 132.40/14j r2 — cross-round, ne pas utiliser ; d'où la **sonde MESO** ci-dessous.

**Sonde de taux par MESO (r1)** : envoyer une variante 14 j et une variante 90 j dont les prix sont à parité à **notre** 8 % (`p14 = p90 × (1 − 0.08×76/360)`). La variante que le bot reprend dans sa réponse révèle le signe de `r̂_s − 8 %` (s'il reprend le 14 j à notre prix, payer vite vaut plus pour lui que 8 % ; s'il reprend le 90 j, moins). C'est gratuit : les deux feuilles sont à C_rel égal pour nous.

**Priors par persona** (appris des 3 points calibrés, à n'utiliser qu'en l'absence de paires, poids 1/3 contre 2/3 pour les paires) : Owner / Export Manager cash-sensible → ~10 % ; KAM / Segment Manager / groupe avec `approval_ladder` → ~6,5 % ; défaut → 8 %. Le parse de la signature (« Thomas Brandlhuber, Owner » ; « Petra Lechner, Key Account Manager ») est trivial.

```python
r_hat = clamp(0.67 * pair_rate + 0.33 * prior if pair_rate else prior, 0.03, 0.15)
st["std"]["_floor"]["interest_rate"] = r_hat   # met à jour le modèle de relation en cours de négo
```

### Coût complet — règle et replis

1. **`cost:<part>` présent dans facts** → `full_cost = unit_cost / 1.02`. Preuve que c'est la formule cachée et pas une coïncidence : ratios 0.9804 / 0.9804 / 0.9805 sur trois fournisseurs indépendants. (Remplacer `SHOULD_COST_RATIO = 0.98` par `1/1.02`.)
2. **Pas de should-cost** → repli conservateur : `fc_est = open_value / (1 + (m_s + 2)/100)`, bande ±4 %, et pour les **floors** utiliser le côté haut (`fc_est × 1.02`) — le floor sert à ne jamais offrir dans la zone de charge, il doit être pessimiste.
3. **Raffinage par son final** : si le bot déclare un cost_floor et se fige à `p_floor`, `fc ≈ valeur(p_floor) / (1 + m_s/100)` — à n'utiliser que comme sanity check de (1)-(2), jamais comme cible (Codex : calibrer sur le résultat ne prédit pas l'inconnu).

### Gain / risque

- Fiabilise le choix de rang (P01 14 j vs P02/P03 90 j) et la position du U-bottom (±0,03 % de valeur par point de taux d'erreur — négligeable ; c'est le **choix de rang** qui porte tout l'enjeu).
- Risque : paires confondues avec concessions (règle : même round uniquement) ; re-tuning des bots en finale → toujours ré-inférer en ligne, les priors ne servent qu'aux 2 premiers rounds.

---

## 3. M3 — Le levier « substantiation » : répondre aux questions scriptées avec des pièces

**Module : `reader.py` (extraction de questions), `adapt.py`, `claims_intel.py`. Priorité P1.**

### Diagnostic

Les bots posent des questions scriptées qui **débloquent leur palier suivant**, et nos agents n'y ont jamais répondu. Preuves mot à mot :
- P01 `7f323228` r4 (final) : *« However, you have still not answered my question regarding a binding volume commitment. Please let us know what volume you can commit to, as **this is the key to unlocking a more favorable price**. »* — le deal s'est fermé à 131.60 (0.995) avec la question pendante.
- P03 `f518d960` r2 : *« Please provide the underlying data for your volume commitment to substantiate this planning certainty. »* + *« Which figures is that based on? »* — jamais fournis ; prix figé 431.63.
- P10 `b84becc1` r2 (final) : *« Please provide the underlying forecasts confirming your volume commitment. »* — jamais fournis ; final 31.50.
- P18 `f8069a19` r2-r3 : *« kindly request that you share the corresponding consumption data or forecasts. »* — jamais fournis ; final 5.40.
- P07 `76f3602d` r2-r3 : *« please provide the actual forecast data for our records »* / *« Could you please share the underlying data for the binding volume of 30,000 bundles? »* — jamais fourni ; final 5.46.
- P18 `dac4d409` r2 : *« as no figures were provided, we ask you to share this data »* puis r3 : **walked_away** (0.000). L'absence de chiffres tue.

### Règle générale

1. **Détection** (`reader.read` + regex de repli, sans LLM bloquant) : `which figures|underlying data|underlying forecasts|which volume can you commit|consumption data|forecast data|substantiate|binding release schedule|which data` → `st["pending_question"] = "volume"|"figures"|"forecast"`.
2. **Réponse au round suivant** : (a) le claim `fc:<part>@<mois>` réservé à cet effet (les « duplicate » sont inoffensifs mais inutiles — le réserver, ne pas le dépenser en r1) ; (b) une phrase d'engagement chiffrée ; (c) **une pièce jointe CSV** construite depuis `forecast_lines`/`po_lines` (données vraies). api.md : les attachments md/csv/json **sont lus** et ne consomment **pas** de slot de claim. C'est le seul canal de « preuve » illimité de l'arène.

```
We commit to a binding volume of {vol} pcs per year over {months} months, backed by our
official forecast of +{fc.change_pct}% for {part} ({fc_id}). The attached CSV shows the
monthly demand plan we transmit to suppliers.
Attachment: forecast-{part}.csv  (month, qty, source fc_id)
```

3. Réservation du `fc` : si `volume_per_year` est négociable **ou** si les signaux intel contiennent `volume_focus|approval_ladder|capacity_tight` **ou** si le bot demande « which volume » → ne pas citer le fc en r1, le garder pour la réponse. Sinon, citer en r1.
4. Règle du « jamais vague » : tout e-mail qui dit « the referenced market data supports this level » sans chiffre ni ID a produit un walk (P18 `dac4d409`). `guard.py` doit **bloquer** toute phrase contenant « data/figures/records » sans ID `xxx:` ni nombre dans la même phrase.

### Gain / risque

- C'est le mécanisme qui manque entre nos plateaux et les records : P01 le dernier 0,3-0,5 € (1.000 exact), P03 +0,02-0,03, P10 +0,02, P18 +0,05-0,15, P07 +0,03-0,05.
- Risque ~0 : pire cas = duplicate/irrelevant, sans coût mesuré. `[SONDE P03]` (le cas le plus propre pour isoler l'effet : price_frozen + approval_ladder + fc dispo).

---

## 4. M4 — Claims : fenêtres drivers et discipline anti-doublons

**Module : `claims.py`, `claims_intel.py`, `guard.py`. Priorité P1.**

### Claims « driver-window »

Les bots listent leurs drivers dans l'ouverture : *« LCI-C rose 2.7 % in twelve months and is 30 % of our cost »*, *« PPI-C2611 rose 13.5 % … 42 % »*, *« CU-NOTATION rose 47.7 % … 20 % »*. Le checker accepte `2 × idx, one series, ≤ 12 months apart, ending within the last 12 months`. Règle :

```python
def driver_window_claims(case, drivers, idx_values, asof="2026-09"):
    out = []
    for series, weight, bot_claim_pct in drivers:
        best = None
        for end in months(series, last=asof, max_age=12):
            for start in months_between(end-11m, end-1m):
                chg = idx[end]/idx[start] - 1
                if chg < bot_claim_pct - 0.005:            # seulement si PLUS FAVORABLE que son récit
                    best = min(best or (chg,start,end), (chg,start,end))
        if best: out.append(claim("index_change", [f"idx:{series}@{best.start}", f"idx:{series}@{best.end}"], pct=best.chg))
    return out
```

- Ne jamais citer une fenêtre **défavorable** (elle arme le bot). Si aucune fenêtre n'est favorable → pas de claim driver.
- Figure exacte recomputée depuis `index_values` (tolérance ±0,5 pt) ; en cas de doute (release Sunday), citer les IDs **sans chiffre** (« the data's own value is taken ») — zéro risque de `contradicted`.
- Effet attendu : ramollissement du palier de 0,3-1,5 € (P01 : PPI-D351 −3,7 % a produit −5,50 € au r2 de `3a0b48ea`). `[SONDE P02]` (CU-NOTATION), `[SONDE P03]` (PPI-C2611).

### Discipline (preuves chiffrées de la calibration publique ~100 sessions)

- **1 claim par type par message** : P07 `76f3602d` r1 : 3 claims `volume_change` → `verified / duplicate / duplicate` — 2 slots brûlés.
- **Max 3 par message, 1 nouveau par round après r1** (la calibration : plus n'apporte rien).
- **Ordre de préférence** : notice_period (7/7) > should-cost (11/14) > forecast/volume (37/48) > rival quotes (21/31) > index (47/81) > **price_history po: (4/44 — dernier recours, ou jamais)**. Nos runs P04/P11 confirment : po: → « it holds, but it does not change our calculation ».
- **IDs à usage unique par cas** ; rival quote : une fois **par fournisseur** (règle explicite api.md) → en RFQ, la même offre rivale peut être citée à chaque autre soumissionnaire.
- **news: négatives** sur le fournisseur (margin_protection) : un claim `news:` vérifie « that it is about this supplier » — gratuit en slots, à tester en prose d'appui.
- `doc:`/`ctr:` de notice : 7/7 d'acceptation — toujours en r1 sur les price_increase avec lettre.

---

## 5. M5 — Machine à statuts : agreed, final, nudge, timeouts

**Module : `agent.py` (réécriture de la boucle `decide`), `runner`. Priorité P0.**

### `agreed` — sémantique exacte et conversion

api.md : *« agreed (it offers exactly your terms - you still accept) »*. L'analyse des replays tranche le débat H1/H2 : **le bot prend le meilleur pour lui de NOS packages, aux termes exacts** (P02 : notre variante 355.93/14j/index reprise à l'identique ; P05 : 28.77/14j/28 ; P18 : 5.30/60j/db5 après miroir). Conséquences :

1. Toute feuille envoyée peut devenir le deal → **toute feuille est pricée à C_rel = target** (M6). Plus jamais le désastre P02 r1 (variante 355.93/14j/index à C nu égal mais +38 k€ de relation + 17,5 k€ de risque d'index).
2. À réception d'un `agreed` : calculer C_rel. Si `≤ target` → **accepter immédiatement** (prendre la victoire, score verrouillé). Si `> target` → **conversion à valeur-parité** : feuille unique sur le rang C-min (M1), au prix qui conserve la valeur cash de l'agreed au taux r̂_s. Preuves que le bot re-price sans rompre l'accord : P02 `1772c59e` r2 : *« That change is possible at the price below; **our agreed offer stands too**. Alternatively, with Zahlungsziel 14 days net: €355.93 »* — agreed 355.93/14j → re-pricé 358.95/60j = 355.93 × (1 + 0.066×46/360) ✓. Puis accepter sa réponse (ou l'ancien agreed : tentative d'accept sur l'ancien ID ; si 422 « stale » — gratuit, aucun round consommé, api.md — accepter le standing courant ; seulement si > 20 s de clock).
3. **Supprimer `pushed_agreed`** (pousser plus bas après un agreed) : c'est la cause directe des deals 344-347 (0.0-0.01) ; l'agreed est « sticky » de toute façon (P05 : *« Our agreed offer stands »* ×4).

### `final_offer` — espace d'actions restreint

api.md : *« final_offer (push further and it may walk) »*. Preuves : P02 `f712b503` — counter 361.21 après son final 372.23 → back office *« My call: hold … we withdraw »* → no_deal 0.000. P18 `dac4d409` — counter 5.45 après final 5.50 → walked_away. **Contre-exemple** : P18 `f8069a19` r4 — **miroir de sa propre alternative** (5.30/60j/db5) après final 5.40/90j → *« We are pleased to confirm the acceptance of this package »* (agreed). Règle :

```
si status == final_offer:
    actions_permises = { accepter le standing,
                         miroir d'une alternative offer:*-a meilleure en C_rel (feuille = ses termes exacts),
                         accepter un ancien agreed (tentative, 422 gratuit) }
    jamais: counter sous le prix final, question vide, timeout   # les trois mènent au walk
```

Le miroir ne se fait que si `C_rel(alt) < min(C_rel(standing), projection_du_final)` — contre-exemple P10 `57afc7b5` : l'alternative 31.90/54j (C 1 537 008) était **pire** que la projection 31.5/56j (0.679) → ne pas miroir, négocier le prix.

Et **un timeout après un final = walk** (P10 `57afc7b5` r2 : *« As we have not received a response to our final offer, we are withdrawing »* → 0.000) → le watchdog (M7) sert les fils `final_offer` **en priorité absolue**.

### `open` — le nudge pré-final

Le checker `agreed` du bot semble accepter nos feuilles ≥ son plancher assoupli par les claims/réponses. Donc au pénultième round prévu, **une** feuille unique à `p* = min(price_for(meilleure_structure, target_C_rel), standing_price − tick)`, `tick = max(0.01, 0.002×prix)`, bornée par le U-bottom :

- P04 : standing 4.94/90j/24m → feuille 4.93 → si agreed : C 196 453 ≤ c_best 196 529 → **1.000** (1 centime = 400 € = 0,17 pt de score !). Pire cas : il tient 4.94, on accepte au round suivant (0.860 conservé). `[SONDE P04]`
- P01 : 130.85/Apr/14 → C ≈ 1 096 8xx → 1.000 (le final accepté était 131.20). `[SONDE P01]`
- P03 : 430.9/90j → rel tombe à 0 (marge > 8 %) → ~0.955.
- Une seule fois par fil (`st["nudged"]`), jamais après un final, jamais sous le U-bottom.

```python
if status == "open" and offers >= 2 and not st["nudged"] and moves_left(case, events) > 2:
    s = best_structure_rel(case, stdC)
    p_star = round(min(eco.price_for(case, s, target_C_rel, stdC),
                       standing_price - max(0.01, 0.002*standing_price)), 2)
    if p_star >= eco.cheapest_price(case, s, stdC, 0.01, hi) and p_star < standing_price:
        st["nudged"] = True
        return send_single_sheet(s, p_star)
```

### Historique complet des feuilles

Conserver **toutes** les feuilles du bot (standing + `offer:*-a` alternatives) avec leur C_rel et leur statut ; le meilleur sheet historique est toujours candidat à l'acceptation (P18 : l'alternative ignorée valait 3 332 € — Codex ; P10 : `offer:70410-1-a` 31.90/54j). Les IDs peuvent devenir stale → miroir (pas besoin d'ID).

### Keepalive

Les questions vides gardent un fil vivant mais **peuvent déclencher un final** (P05 `b4400695` r5 : keepalive → 70210 final) et consomment un move. Règle : ≤ 2 keepalives, uniquement en RFQ pré-final, jamais sur un fil mono-fournisseur proche du final.

---

## 6. M6 — MESO 2.0

**Module : `economics.best_for_target`, `agent._sheets`. Priorité P1 (petit).**

1. **Variantes à C_rel égal** (pas C nu) : chaque variante est pricée avec `stdC` et cappée au U-bottom **de sa propre structure** (`_floored` par feuille — déjà en place, vérifier qu'aucun chemin ne le contourne : « the floor bypassed by an alternative path », lot E).
2. **Variante jackpot en r1** : une feuille exactement au U-bottom de la meilleure structure. Si le bot l'accepte → score ~1.0 immédiat ; s'il la refuse, aucune perte (c'est une feuille floorée, C_rel ≤ c_s_rel).
3. **Sonde de préférence** (M2) : variante 14 j vs 90 j à parité 8 % → son choix révèle son taux.
4. **Guidage du choix** : le bot prend « le meilleur pour lui » → si on veut qu'il choisisse la structure cible, lui donner une valeur cash marginalement supérieure (+0,1 %) aux autres variantes. Micro-gain, gratuit.
5. Rester à 3 feuilles max (422 sinon) ; varier sujet/corps à chaque round (cache serveur) ; ne jamais renvoyer des feuilles identiques deux fois (« We note that your proposed term sheets remain unchanged » → hold, P02 `32b3b929`).

---

## 7. Cas relationnels — P01, P02, P03 : politique exacte

Rappel des constantes recalées (exactes à ±4-13 €) : P01 : fc = 132.64/1.02 = **130.04**, r = **9,6 %**, m_s = 3, pp = 15 470. P02 : fc ≈ **367,6**, r = **6,6 %**, m_s = 0,5, pp = 31 920. P03 : fc ≈ 399,9/1.02 = **392,1**, r = **6,1 %**, m_s = 8, pp = 28 360.

### P01 (attendu 0.998-1.000)

- Structure : **Apr/14j** (fond du U 130.65 ; Nov/14j 128.95 et Jan/14j 129.43 équivalents en C_rel ; jamais 60/90 j : U-bottom ~133 → la régression 0.953).
- r1 : feuille [130.65/Apr/14j (jackpot) + variantes] ; claims [notice_period doc+ctr (7/7), should_cost 132.64 (11/14), PPI-D351 −3,7 % (fenêtre 2025-08→2026-08)] — ces trois-là ont déjà produit 137.90→132.40.
- r2 : réponse à la question volume : fc +10,1 % + phrase d'engagement + **CSV forecast joint** (M3). Ne pas laisser la question pendante jusqu'au final (coût mesuré : 131.60 au lieu de 131.20, voire le 1.000).
- r3-r4 : schedule C_rel ; nudge **130.85/Apr/14** → si agreed, C ≈ 1 096 8xx ≤ c_best → **1.000** ; sinon accepter son final ~131.2 → 0.998.
- À ne jamais faire : deal Nov/60 (rel + payment), ancre sur la mauvaise structure, laisser `pushed_agreed` actif.

### P02 (attendu 0.734, stretch 0.85)

- **Toujours la clause CU-NOTATION db5** : le bot la requiert pour ses meilleurs prix et sa remise vaut ~11 €/unit (355.93/14j/index vs 367.05/14j/sans) pour un coût réel de ~2,85 €/unit (risque 0,8 % du spend à db5, path +5 % → index_cost = 0). La ladder « no Preisgleitklausel » (367.05/14j ↔ 372.23/90j) est strictement dominée.
- Chemin : ancre 356.5/14j/db5 (+ variantes sonde de taux) → `agreed` probable ~355.93/14j/db5 → **ne pas accepter** (C 2 254 124, 0.607) → **conversion feuille unique** : « 90 days net, CU clause db5 » à 360.89 (valeur-parité à 6,6 %) → il re-price/agrée → accepter → C 2 248 050 → **0.734** (house 0.74).
- Stretch vers le record 0.847 (C 2 242 757 → valeur cash ~355,6, soit −1,4 € sous son plancher observé) : r1-r2 claims [fenêtre CU-NOTATION la plus favorable ≤12 mois (M4), fc +11,9 %, réponse « which figures » + CSV]. `[SONDE P02]` : mesurer si le palier cède ; si non, 0.734 est le plafond et on le verrouille proprement.
- À ne jamais faire : offrir sous 356.5/14j/index (zone de charge : 344-347 = 0.00-0.01) ; counter après final (walk `f712b503`) ; accepter le 14 j final.

### P03 (attendu 0.94-0.963)

- Structure : **90j / 24 mois / 4 580 pcs** (36 mois = même C, à garder comme chip gratuit ; jamais 5 496 : +790 k€ d'achat inutile ; jamais 14j : +40 k€ d'intérêts).
- Échelons observés : 426.97/14j (0.869) → 430.17/60j (0.900) → 431.63/90j (0.935) — valeur-parité à ~6 % ✓. Le record 0.963 = C 3 921 583 ≈ 430.2/90j, soit −1,4 € sous le gel déclaré.
- Politique : ancre 418/90j/24m (fond du U) ; claims r1 [should_cost ~399.9, price_history 400.19/412.74 — déjà vus « taken into account », fc +10,3 %] ; r2 : **réponse de substantiation** (fc + CSV mensuel) + demande d'approbation management (INTERNAL_RE : « reviewed internally / approval / corporate policy » — déjà câblée, la garder) ; r3 : chip 36 mois ; r4 : nudge 430.9/90j (à ce prix la marge ≥ 8 % → rel = 0 → C 3 923 9xx → 0.955) ; sinon accepter 431.63/90j → 0.935.
- `[SONDE P03]` : isoler l'effet substantiation (bot le plus déterministe du paquet).

---

## 8. Plateaux — P04, P07, P08, P10, P11, P18

### La boucle générique de découverte (identique sur cas caché)

```
r1 : MESO [jackpot U-bottom ou ancre, + 2 variantes un-levier dont la sonde de taux]
     + 2-3 claims triés par taux d'acceptation (§4) + 1 question coût/décomposition
r2 : lire la réponse -> paires de prix -> r̂_s (M2) ; questions -> pending (M3) ; signals (gel, cash, ladder)
r2-r3 : répondre aux questions (fc réservé + CSV) ; claims driver-window ; concessions en C_rel
r3-r4 : chip gratuit (mois > horizon) ; nudge -1 tick sur la structure C-min
fin : accepter / miroir selon la machine à statuts (M5) ; closing = meilleur sheet historique C_rel < c_alt
```

Tout est dérivé à chaud : signaux (persona, regex, intel), échelons de prix, questions, rien de codé par cas.

### Tableau par cas (cibles C exactes ; décompositions des records = nos meilleures estimations)

| Cas | C_open → C_best | Palier observé | Levier manquant | Cible | Gain |
|---|---|---|---|---|---|
| P04 | 198 846 → 196 529 | final 4.94/90j/24m = 196 853 (0.860) | **nudge 4.93** → 196 453 | **1.000** | +0.14 |
| P07 | 391 027 → 299 241 | final 5.46/90j/36m (0.715) ; alt 5.41/14j (0.687) | approval + substantiation + pas plus gros ; record ≈ 5.31/90j | 0.75-0.81 | +0.04-0.10 |
| P08 | 1 135 887 → 960 309 | clause 5.25/90j/db0/36m (0.659) ; db5 → 997 722 (0.787) ; **fixed 5.17/90j/24m → 973 697 (0.924)** | demander le prix FIXE 24m (couverture matière jusqu'à mars 2027 : doc:20260706-70710-M1 en **contexte**, pas en check) + fenêtre AS-14404 + miroir db5 | 0.79-0.92 | +0.13-0.26 |
| P10 | 1 932 492 → 1 328 927 | final r2 31.5/56j (0.679) | **ne jamais demander 42 j** (prime +2,3 € vs late cost 0,72 €/unit) ; substantiation r2 (il finalise à r2 !) ; nudge 31.2 | 0.69-0.71 | +0.01-0.03 |
| P11 | 817 578 → 722 500 | palier 45.0/ppm300/cb0 (0.794) | wording (ci-dessous) ; record ≈ 44.4 | 0.79-0.89 | +0.0-0.09 |
| P18 | 295 173 → 222 651 | 5.30/60j/db5 (0.575) ; 5.40/90j/db5 (0.576) | gros pas + substantiation + MESO fixe-vs-clause ; record ≈ 5.15/90j/db5 | 0.60-0.73 | +0.03-0.15 |

- **P10, règle spéciale** : son `final_offer` arrive à **r2** (`b84becc1`) et un timeout post-final = walk (`57afc7b5`). Tout doit être compressé en 2 rounds : r1 = structure complète (23 400 / 24 m / **56 j**) + should-cost 24.31 + fc ; r2 = CSV forecast + nudge. Mémoire fournisseur : stocker `finals_at_round` (médiane) → compression automatique du schedule sur les bots rigides (« standard procedure », `approval_ladder`). Pareil pour P04 (final possible dès r2, `c8387f21`).
- **P11, wording** : supprimer la ligne « The enquiry fixes payment at 60 days net » — le bot la retourne en excuse de palier mot pour mot : *« You say 60 days payment is fixed, but that really hurts our cash flow and limits what we can do »*, *« Since you can't change the 60 days payment … we don't have much more room on the price »* (les deux replays). Remplacer par une concession prose gratuite (signal `buyer_late_payment`) : *« we commit to paying your invoices on the due date, without exception »*. Demander une fois le rapport 8D (document prévu par les règles qualité). Rester sur la piste **ppm300/cb0** (la piste 1500/cb500 est empoisonnée : 48.0 → 0.314 ; le bot la re-price à la hausse) ; nudge 44.5-44.9. `[SONDE P11]`
- **P18, le piège à 0** : 11 no_deal/0.000 dans nos runs — tous par counters post-final (`dac4d409`) ou abandon. Règle M5 stricte + gros pas (+0,3 €/round, pas +0,02 : « does not reflect a substantial move ») + réponse « consumption data » au r2 + miroir de ses alternatives. `[SONDE P18]`
- **P08, hedge** : la lettre de couverture (doc:20260706-70710-M1) est un `doc:` de **contexte** (« IDs of meeting notes … are context, not checks ») → prose libre sans slot : *« your letter of 6 July confirms your material is covered until March 2027; a fixed price over 24 months therefore carries no material risk for you »* + MESO [fixed-24 / clause-db5-36] → son choix révèle le vrai plancher. `[SONDE P08]`
- **P04/P07 (routine, distributeurs, « Preisliste and discount tiers »)** : demander en prose ce qui déclenche le palier suivant (volume/durée) ; sinon le nudge −1 centime est le play mécanique (P04 : +0,14 pour 1 cent). `account_exit` (P04) : ne jamais menacer de partir (alternative 5.04 > 4.96, faible).

---

## 9. RFQ (P05) — le playbook « ratchet »

**Module : `agent.py` (branche RFQ), `runner`. Priorité P1. `[SONDE P05]` première.**

### Diagnostic (preuves du replay `c258812a` / `b4400695`)

1. Le bot réagit aux citations rivales en **deux temps** : back office *« The buyer shows a much lower rival quote. **I give half the step now and check the rest**. »* puis *« team Checked: **give the rest of the step**. »* → après une chute déclenchée par une citation rivale, ne faire qu'**un pas symbolique** au round suivant et encaisser le reste.
2. Le plancher réel est dans la **prose**, pas la feuille : *« I'll do **28.00 EUR** per unit for 14 days payment and 28 days lead time »* alors que la feuille dit 28.77.
3. Notre `agreed` précoce (28.77 au r2) a **verrouillé** le prix : ensuite *« Our agreed offer stands »* ×4. Il ne faut jamais laisser un soumissionnaire agréer avant la fin du ratchet : toute feuille envoyée avant la clôture doit être **sous son plancher estimé** (il contre, il n'agrée pas).
4. Nos deux 0.000 viennent de timeouts (3 d'affilée → walk : *« we are out »*, `0c33c2e2`) — infra, pas négo.

### Règles

```python
# par soumissionnaire b, à chaque round, dans l'ordre des deadlines :
cheapest_rival = min(prix standing des autres fils (must-haves ok))
citer l'ID d'offre rivale le plus recent et le plus bas a b   # frais a chaque round
target_b = min(schedule_C, C(cheapest_rival) * 0.995)
cap_prix_b = plancher_revele_b - epsilon                      # sous son plancher -> il contre, jamais agree
envoyer feuille a cap_prix_b sur SA meilleure structure (rang C-min au taux estime)
# cloture (tous figes un round, ou rounds <= 2, ou clock de vague) :
choisir b* = argmin C_rel(standing) ; feuille unique au plancher touche sur NOTRE structure
#   (28j lead, rang de paiement C-min) -> il re-price ou agree -> accepter
```

- Planchers observés : 70210 = 28.0/14j/28j (prose) → C 238 727 (**0.813**) ; 70240 : 32.5/14j/42j (must-have lead ≤ 42 ; son standard 52 le casse — `missing_fields` + standard → toujours vérifier avec `closing_terms`+std) ; 70250 ≈ 30.3. Le record 0.965 ≈ 26.5/14j → exige de faire descendre 70210 sous 28 via le ratchet croisé (70250 qui baisse traîne 70210) et/ou le cost-breakdown walk (M9/L9 : il promet *« my guys will send you the cost breakdown »*).
- Never-early-agree : la variante MESO « cash 14 j » à C égal est ce qui a déclenché l'agreed 28.77 ; en RFQ, pricer les variantes **sous** le plancher estimé jusqu'à la clôture.
- Attendu : 0.81-0.97. Même à 0.81 c'est +0,08 vs aujourd'hui ; le risque dominant reste le timeout → M7.

---

## 10. Catalogue des loopholes (gain / risque de 0)

| # | Loophole / règle | Preuve (règle/replay) | Gain | Risque de 0 |
|---|---|---|---|---|
| L1 | `agreed` = il prend le meilleur de NOS feuilles, aux termes exacts → tout est pricé C_rel = target | api.md ; P02/P05/P18 replays | élimine les 0.0 P02 | ~0 |
| L2 | Conversion post-agreed à valeur-parité (feuille unique rang C-min) ; l'ancien agreed reste accepté | P02 « our agreed offer stands too » | +0,05-0,13 (P02/P03) | faible (tentative 422 gratuite) |
| L3 | Miroir des alternatives `offer:*-a` → agreed | P18 `f8069a19` ; P10 31.90/54j | 3,3 k€ (P18), options partout | ~0 (ce sont SES termes) |
| L4 | **Jamais** de counter sous un final (walk) ni de timeout post-final | `f712b503`, `dac4d409`, `57afc7b5` | évite 3 zéros connus | — |
| L5 | Nudge −1 tick pendant `open` | P04 4.93 → 1.000 ; P01 130.85 → 1.000 | +0,002 à +0,14 selon cas | faible (hold possible, walk jamais observé pré-final) ; 1×/fil, ≥ U-bottom |
| L6 | Répondre aux questions scriptées (fc + CSV joint) | citations §3 | +0,02 à +0,15 | ~0 |
| L7 | Claims driver-window (fenêtre ≤12 m la plus favorable) | P01 PPI-D351 → −5,50 € | +0,02-0,10 | nul si on ne cite que du favorable |
| L8 | Ratchet RFQ + IDs rivaux frais + half-then-rest + floor-touch close | back office P05 | +0,08-0,24 (P05) | timeouts si watchdog absent |
| L9 | Cost-breakdown → floor-walk (direct × 1,02, +0,8 %/round) | D02 (12.76 → C_best 13.06) | fort quand la pièce arrive | activer SEULEMENT si breakdown réel reçu et goal ∉ relation (régression sandbox sinon) |
| L10 | Mois > horizon = concession gratuite (`min(M/12, H)`) | cost.py `_years` ; P07 −0,04 | petit, gratuit | 0 |
| L11 | Rang de paiement par r̂_s vs 8 % | P03 −26 358 € à 90 j | mécanique | faible (calculer les deux rangs en C_rel) |
| L12 | Date d'effet tardive = unités au prix courant | cost.py `_units_before` ; P01 | inclus dans la grille | le bot peut facturer les dates → comparer les échelons dates |
| L13 | Clause db ≥ |path| quand le bot la veut : coût ~0, sa remise ≫ | P02 : 11 €/unit pour 2,85 € de coût | +0,13 vs no-index (P02) | 0 (index_paths du cas = publié) |
| L14 | Doublons : 1 claim/type/message ; 1 nouveau/round ; rival 1×/fournisseur ; jamais re-citer | P07 verified/duplicate/duplicate | slots préservés | 0 |
| L15 | Cache serveur : sujets suffixés par round → réponses fraîches ; NONCE en pratique | « the server caches identical messages » | évite réponses périmées | 0 |
| L16 | 422 gratuit : valider les feuilles côté client (snap/options) ; accept stale-id → 422 → fallback standing | api.md 422 | aucun round perdu | 0 (clock : seulement si > 20 s) |
| L17 | Timing : réponses < 10 s → plus de rounds avant le cap ; last counter à cap−140 s ; closing à cap−40 s | 8 min/vague, ~60 s/réponse bot | +1-2 rounds utiles | 0 |
| L18 | Must-haves via `closing_terms` + std (`missing_fields` → standard) | P05 lead 52 | évite le 0 systématique | — |
| L19 | Score clippé à 1.0 : inutile (et risqué) de dépasser c_best | cost.py `score` | arrêter la négo à target | 0 |
| L20 | Release Sunday + `case.facts` fusionnés dans le registre de claims | api.md « Hidden cases may cite its facts » | claims valides sur cas cachés | contradicted (perte de confiance) si absent |
| L21 | `X-Move-Id` idempotent → retries réseau sûrs | api.md | robustesse | 0 |
| L22 | No-deal = alternative : ne jamais accepter pire que c_alt (P07 : walk = 0.121 !) ; sur cas sans alternative : accepter le meilleur standing valide au cap | api.md | P07/P15 | 0 |
| L23 | Message sans feuille = fil vivant sans concession | api.md | keepalive | déclenche des finals → ≤2, pré-final |
| L24 | Guidage MESO : la variante qu'on veut lui voir prendre = la meilleure **pour lui** (+0,1 % valeur) | « it picks the package that is best for it » | micro | 0 |
| L25 | Persona → famille de script → priors (cash / ladder / tiers / eagerness) | signatures des replays + profils | meilleure r1 | faible |
| L26 | « we hold our Angebot » si pas trop petit → pas visible ≥ 0,4 % du prix | replays | évite les holds | 0 |
| L27 | Watchdog : fils `final_offer` servis en priorité ; alarme à 40 s | P10 walk post-timeout | élimine les zéros timeout | 0 |
| L28 | `facts` cachés du case file citable | api.md case file | claims sur cas cachés | 0 |
| L29 | Déterminisme + cache → sondes reproductibles ; mais « identical messages need not get identical replies » → règle des 3 observations pour les flags mémoire | api.md | pas de sur-apprentissage | 0 |
| L30 | **Interdit** : lire `/v1/events`, `/v1/results`, `/leaderboard`, `/screen` pendant le final ; attaques ; multi-clés ; humain dans la boucle | règles 1 et 7 | — | disqualification |

Interdits respectés ; tout le reste est explicitement permis (règle 2 : *« Everything else counts - including weaknesses you find in our bots »*). Garder les e-mails professionnels : le jury lit les replays.

---

## 11. Plan des 12 heures + budget des 10 sondes + risques du dimanche

### Phasage

**Phase A (~3 h) — cœur :** M1 (C_rel partout : `_anchor`, `decide`, `_accept_best`, `closing`, `best_at_price`), M2 (`infer_rate` + priors persona + fc fallback), M5 (machine à statuts : agreed-conversion, final = accept/miroir only, nudge, historique des feuilles), schedule compressé par l'horloge de vague, reconstruction d'état sur reprise (`offers` = nb de messages buyer avec feuilles). Harness de régression **offline** : rejouer les ~150 sessions loguées à travers le nouveau `decide()` et asserter : jamais de retraite, jamais de counter post-final, jamais de feuille sous le U-bottom, jamais de must-have cassé, jamais de feuilles identiques 2×, toujours une action ≤ 10 s.

**Phase B (~2 h) :** M3 (extraction questions + réservation fc + génération CSV forecast/po), M4 (driver-window + dédup par type + ordre de préférence + ban « vague data » dans `guard.py`), ratchet RFQ (M8), watchdog + LLM reader hors chemin critique (regex fallback instantané), loader release Sunday + fusion `case.facts`.

**Phase C (~2 h) :** sandbox D01/D02 (gratuit) + harness replays ; stabilisation ; **tag git de rollback** ; chaque changement derrière flag `PEGASUS_*` avec défaut = comportement validé.

**Phase D (soirée) — sondes (quota, 10 max), par ordre de priorité :**

| # | Sonde | Hypothèse testée | Critère de succès |
|---|---|---|---|
| 1 | **P05** | ratchet + no-early-agree + floor-touch | ≥ 0.81 (stretch 0.9) |
| 2 | **P02** | ancre 356.5/14j/db5 + conversion 90j + claim CU-window + substantiation | ≥ 0.734 (stretch 0.847) |
| 3 | **P01** | ancre floorée 130.65/Apr/14j + réponse volume r2 + nudge 130.85 | ≥ 0.998 (stretch 1.000) |
| 4 | **P03** | substantiation (fc + CSV) + PPI-C2611 window + chip 36 m | ≥ 0.94 (stretch 0.963) |
| 5 | **P18** | gros pas + substantiation + MESO fixe/clause + miroir | ≥ 0.60 (stretch 0.73) |
| 6 | **P08** | prose hedge + fenêtre AS-14404 + demande fixed-24 + miroir db5 | ≥ 0.79 (stretch 0.92) |
| 7 | **P11** | sans la ligne « payment fixed » + 8D + promesse de paiement | ≥ 0.80 (stretch 0.885) |
| 8 | **P10** | fc+CSV à r2, 56j dès r1, nudge 31.2 | ≥ 0.69 |
| 9 | **P04** | nudge 4.93/90j/24m | ≥ 0.87 (stretch 1.000) |
| 10 | **P07** | approval ask + CSV + rythme + 36 m | ≥ 0.75 |

Si quota tendu : couper 10, 9, 8 (petits gains). **Aucune sonde sans passage préalable du harness + sandbox** (nos zéros quota brûlés étaient des bugs d'infra). Lire chaque replay après sonde (les « reasons » disent ce qui a mordu).

**Phase E (dimanche) :** 08h05 télécharger et indexer la release Sunday (test unitaire claims sur ses IDs) ; 09h00 pre-flight (1 session, hors budget) ; 10h30 répétition finale (runner complet sur sandbox) ; 11h30 gel + démarrage du runner ; 12h00 vague 1.

### Risques du dimanche et parades

1. **Bots re-tunés** (« new suppliers and settings », jusqu'à 1/3 de combos inédits) : priors légers, ré-inférence en ligne systématique (paires, planchers, questions) ; les règles sont indexées sur les **signaux**, pas sur les cas.
2. **Horloge** : lire `seconds_left` serveur (api.md : « read it, don't assume it ») ; schedule compressé à `R = min(round_limit, ⌊(seconds_left−60)/70⌋)` rounds, fractions [0.35, 0.6, 0.8, 0.92] ; last counter à cap−140 s ; closing à cap−40 s.
3. **60 s par réponse** : décisions 100 % code (reader LLM async, résultat consommé au round suivant ; regex fallback immédiat) ; watchdog par fil avec file de priorité (final_offer > open > keepalive) ; alarme à 40 s → envoi du meilleur geste sûr (miroir/accept/nudge pré-calculés).
4. **Latence bot ~60 s** → 5 rounds max par fil ; accepter plus tôt si nécessaire.
5. **Crash** : au redémarrage, `GET /v1/sessions?set=final` → 409-resume → reconstruction d'état depuis les threads ; `X-Move-Id` sur chaque POST.
6. **429** (10 sessions / 10 rps) : throttle + ouverture des cas en file au gré des clôtures.
7. **Must-haves** : vérification `closing_terms`+std à l'acceptation (L18) ; jamais d'accept sur une feuille incomplète.
8. **Release Sunday absente/illisible** : try/except → paquet v1 + `case.facts` seuls ; aucun crash.
9. **Score 0 résiduels** : les trois sources historiques (agreed sous coût, counter post-final, timeout) sont chacune couvertes par une règle dure (M1 floors, M5, M7) — à asserter dans le harness.

### Ce qu'on ne touche pas

Le LLM narrator (off), `claims_intel` hors nouvelles règles M4, la mémoire cross-sessions (règle des 3 observations — L29), le guard existant (on ajoute le ban « vague data » et la fusion `case.facts`, rien d'autre), le playbook `target_c` par case_id (**exclu de la config finale** : apprentissage par ID, contraire à la contrainte et inutile sur cas cachés — les mécanismes ci-dessus le remplacent).

Avec M1+M5+M7 seuls, les zéros disparaissent et la moyenne hosted passe de ~76 à ~82-84 ; avec M3/M4/M8 validés par les sondes, la zone 85-88 est atteignable — soit le niveau du leader actuel, avec un agent dont chaque nombre est dérivé à chaud et donc transférable aux cas cachés.