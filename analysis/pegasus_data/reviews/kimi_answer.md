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