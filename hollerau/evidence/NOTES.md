# Passation : couloir Économie et preuves

Nevil (avec Claude), samedi 10/10/2026. Branche locale `nevil/evidence` de `hollerau-agent`, **rien de commité, rien de poussé**.

## Règles de travail (à respecter)

- **Freeze** : les modifications sont limitées à `hollerau/evidence/` (`/freeze`, `/unfreeze` pour le lever). On ne touche ni à `hollerau/contracts.py`, ni à `arena_kit/`, ni à `tests/fixtures/`.
- **Aucun push, aucun commit sur `main`, pas de `/ship`.** Branche locale `nevil/evidence` uniquement. L'intégration se fait chez Icham.
- **Aucune session sur arena.tacto.ai**, ni entraînement ni sandbox (règle absolue du vault : seul Icham valide un lancement). On ne contourne jamais le verrou `HOLLERAU_VALIDATED`. Tout ce qui suit tourne hors ligne.
- Le data package est lu en **lecture seule**. Il est cherché dans `ARENA_DATA`, puis dans `data/package` de ce dépôt, puis dans `~/Projets/negotiation-arena-kit/starter-kit/data/package`.

## Ce qui est fait

| Fichier | Contenu | État |
|---|---|---|
| `__init__.py` | Description du couloir | fait |
| `facts.py` | `package(data)` (cache des seuls succès), `facts_of`, `asked_price`, `stake_price` (min. du prix courant et du prix demandé), `comparable` (une pièce, même `price_unit`), `case_start`, `release_rows`, `check` qui ne lève jamais | fait |
| `notice.py` | `notice` : préavis de la lettre < préavis du contrat, `supports=effective_date` | fait |
| `quote.py` | `quote` : devis du cas (`refs` + alternative), même pièce, autre fournisseur, **moins cher que le prix en jeu** | fait |
| `scorecard.py` | `scorecard` : dernière ligne `sc` (déjà glissante sur 12 mois), carte rouge ou orange, ppm > 1 000 ou OTD < 80 % | fait |
| `index.py` | `index` : fenêtre de 12 mois, une série par claim ; hausse justifiée si pondéré ≥ demande − 1 point | fait |
| `orders.py` | `orders` : première et dernière commande des 24 derniers mois, si le prix a déjà monté de 3 % ou plus, sans les lignes `stale_condition` | fait |
| `forecast_cost_news.py` | `forecast_cost_news` : should-cost (marge > 15 %), prévision en hausse ≥ 5 %, news qui affaiblissent le fournisseur | fait |
| `compile.py` | `compile_evidence(case, data)` : notice, quote, scorecard, index, orders, forecast_cost_news, chaque claim vérifié, chaque ID une seule fois | fait |
| `economics.py` | `compile_case(case, standard=None, data=None)`, `lever_price`, `estimate_supplier`, `relationship_risk` | fait, D3 appliquée |
| `signals.py` | `signals(case, data)` pour le planificateur, jamais envoyé comme claim | fait |
| `tests/` | `test_evidence.py` (17), `test_compile_case.py` (61), `test_families.py` (40), `test_hardening.py` (22) | **140 verts** |
| `PLAN-compile_case.md` | Plan de `compile_case` + rapport `/plan-eng-review` (D1, D2) | revu, codé |

`Claim` et `Economics` viennent de `hollerau.contracts` (non modifié).

## État des tests

```bash
cd ~/Projets/hollerau-agent
PYTHONDONTWRITEBYTECODE=1 uv run --offline pytest -p no:cacheprovider hollerau/evidence/tests -q   # 140 passed
uv run --offline ruff check hollerau/evidence && uv run --offline ruff format --check hollerau/evidence   # propres
```

- **Toujours lancer avec `PYTHONDONTWRITEBYTECODE=1`.** Des fichiers `__pycache__` sont suivis par Git dans le dépôt (y compris dans `arena_kit/`), et une exécution normale les réécrit. Icham doit ajouter `__pycache__/` au `.gitignore` et les retirer de l'index.

## Décisions

- **D1, `cost` sans relation.** `Economics.cost(terms)` = `arena_kit.cost.total_cost(case, terms, standard)`, **sans estimation fournisseur**, donc sans terme `relationship`.
  - Mesuré sur la session P01 : avec le should-cost comme coût complet, le deal à 135,40 € coûterait 4 055 € de relation, alors que l'arène facture 0 €.
  - Sans relation, le calcul retombe exactement sur l'arène : `c_deal` = 1 120 579,36 €, `c_alt` = 1 176 178,02 €.
  - Le coût de relation estimé est exposé à part, dans `relationship_risk(terms)`, en `stabilise` / `secure_supply`. C'est un avertissement pour le planificateur, il n'entre pas dans `cost`.
  - À reprendre plus tard : calibrer `full_cost` sur le back office des sessions validées par Icham.
- **D2, `term_options` seulement + warning.** Les 19 cas ont des options pour tous leurs champs négociables hors prix, donc pas de grille inventée. Un champ négociable **sans** options (cas caché) garde la valeur du plan acheteur, n'est pas traité comme un levier, et **émet un warning** (`logging.warning`, avec le nom du champ et le cas) pour qu'on le voie dans les logs du banc et de la finale.

- **D3, leviers au prix demandé (Nevil, 10/10 soir, option A). À reporter dans `Décisions.md` du vault pour Icham.**
  - `compile_case(case)` garde sa signature. Le prix des leviers (`lever_price`) est l'`asked_price` du `trigger_doc`, lu par `facts.py` (`facts.json` + `case["facts"]` pour les cas cachés). À défaut, `current_unit_price`, puis `fallback_unit_price`.
  - `Economics.reference_price` vaut ce prix de levier : c'est à lui que `best_package` et les leviers sont évalués.
  - Ajout compatible : un `data=None` optionnel, pour passer le package avec la release du dimanche. Sans lui, le package trouvé sur disque est utilisé.
  - **P01** : `effective_date` passe de 0 € à **16 263 €** (2027-01-01) et **40 257 €** (2027-04-01) par rapport à 2026-11-01. C'est le levier n°1, devant `payment_days` (18 386 €). P13 : 8 386 €.
- **Correction de `price_unit` (le cas limite 3 du plan était faux).** Les prix des cas sont exprimés dans le `price_unit` de la pièce, comme les données : P14 a un prix de cas de 316,35 €, égal à la dernière commande, pour 100 pièces. On compare donc tel quel, **sans diviser**.
  - `per_unit` est supprimé.
  - `estimate_supplier` lit `unit_cost` brut. Avec la division, P14 aurait eu un coût complet de 3,04 € au lieu de 304,49 €.
  - Les phrases de claims précisent « per 100 pcs » quand il le faut.

## `compile_case` : détails

- `supplier` est passé de `compile_case` à `relationship_risk`, puisqu'avec D1 il n'avait aucun effet sur `cost`.
- **Grille** : `term_options` seulement (D2). Recherche exhaustive (75 combinaisons au plus), descente par coordonnées au-delà de 5 000. Un champ sans options garde le plan acheteur et émet un `logging.warning`. Aucune combinaison valide : `ValueError`.
- **Égalités** : la première option l'emporte. Sur P03, 24 et 36 mois coûtent pareil (horizon de 2 ans), donc `best` = 24. Sur P11 et P12, `ppm_commitment` vaut 0 € quand le chargeback est à son meilleur niveau, ce qui est juste conditionnellement.
- **Contrôle croisé P01** : `c_deal` = 1 120 579,36 € et `c_alt` = 1 176 178,02 €, identiques à l'arène. Le PDF du devis n'est pas dans la fixture : le standard est reconstruit à partir des champs du deal ni négociables ni fixés (ppm 900, chargeback 0). Le poste qualité vaut alors exactement 1 584,36 €.

## Claims par cas (19 cas d'entraînement)

- **notice** : P01 (51 j contre 90 j), P13 (35 j contre 90 j).
- **quote** : aucun sur les 19 cas, car chaque devis alternatif est **plus cher** que le prix en jeu (P01 : 143,22 € contre 138,55 € demandés). Le citer plaiderait pour le fournisseur. La famille sert aux cas cachés (testée avec un devis fictif dans `case["facts"]`).
- **scorecard** : P05 (70210 à 1 863 ppm, 70240 à 62,5 % d'OTD), P06 (70120 74,5 %, 70150 52 % puis 2 842 ppm au trimestre précédent), P09 (56 %), P11 (2 376 ppm, puis 78 % au T2), P12 (4 118 ppm, puis 65,5 %). Chaque ID ne compte qu'une fois : le second argument prend le trimestre précédent.
- **index** : comme avant pour P01 et P13. Il apparaît aussi sur P05, P06, P09, P11 et P12 (électricité −3,7 %), car ces cas n'ont pas de lettre de hausse et seules les séries en baisse sont citées. La ligne précédente « P03 à P18 : aucun claim » de cette note était inexacte.
- **orders** : P14 (285,85 € à 316,35 € pour 100 pièces, +10,7 % en 24 mois), P19 (4,06 € à 4,20 €).
- **forecast_cost_news** : should-cost P06 (194,18 € contre 253,19 €) et P10 (24,31 € contre 29,89 €) ; prévisions en hausse sur 15 cas ; news de capacité libre sur P05 (70250).

**Limite du contrat** : `Claim` n'a pas de champ fournisseur. Dans les RFQ à plusieurs fournisseurs (P05, P06), le planificateur doit router un claim `sc:` ou `news:` vers le bon fournisseur d'après l'ID. Une phrase « Your… » adressée au mauvais fournisseur serait `irrelevant`.

## Signaux (`signals.py`)

Une détection par expressions, fiable parce que les notes du package suivent des gabarits fixes. On lit les notes des 18 mois **avant** la date de la lettre du cas, jamais après. Chaque signal donne ses IDs de source.
- `increase_justified` : P02 vrai (+11,15 % pondéré contre 6,5 %). P01 et P13 faux. **P17 limite** : +7,95 % contre 8 %.
- `material_hedged_until` : P08 (70710) et P14 (70560), March 2027.
- `cash_need` : P11 (appel « Liquidity » + demande de paiement à 10 jours), P06 (70150), P01 et d'autres.
- `committee_above_pct` = 2 : P02, P03, P07, P10, P14, P17, P18, P19.
- `single_source`, `free_capacity`, `full_order_book`, `open_book`, `not_strategic` (P04), `small_account_review`, `list_price_only`, `credit_index_change`.
- `our_late_payments` : 35 à 96 % des factures payées en retard sur 12 mois, de 2 à 13 jours en moyenne, chez presque tous les fournisseurs (KNOWN_ISSUES 9). Ce n'est pas citable.

## Corrections après `/review` (10/10 soir, à la demande de Nevil)

Chaque correctif a son test dans `tests/test_hardening.py`. Contrôle par mutation : en réintroduisant l'ancien comportement (index, forecast, release), les tests concernés échouent.

1. **Règle d'or : jamais d'exception.** `compile_case`, `compile_evidence` et `signals` attrapent les erreurs par étape, par famille et par fournisseur. Ils journalisent (`log.exception`) et rendent un résultat vide : pas de leviers, `best_package` vide, `c_alt` infini, aucun claim pour la famille en échec, signaux à leur valeur vide. `Economics.cost` renvoie l'infini et `must_haves_ok` renvoie `False` en cas d'erreur. Test : 6 cas corrompus (faits absurdes, `buyer` absent, cas vide…).
2. **Must-haves que la grille ne peut pas tester.** Un must-have sur le prix (décision du planificateur), ou sur un champ que seul le devis remplit tant que le standard n'est pas lu, est écarté de la recherche, avec un warning. `Economics.must_haves_ok` garde tous les must-haves. Si aucune combinaison ne passe : warning, et la moins chère est rendue au lieu d'une `ValueError`.
3. **Valeurs nulles** : toute ligne de faits avec un champ nul ou absent est ignorée (`has()`). `check()` renvoie `False` au lieu de planter.
4. **Release du dimanche.** Les documents (`data/documents.csv` de la release) et les commandes (`data/po_lines.csv`, si présent) sont lus en plus de la SQLite ; les news arrivent par `facts`. La fenêtre des notes et des news court jusqu'au **début du cas** (`case["start_date"]`, sinon le fait daté le plus récent, release comprise), et non plus jusqu'à la lettre. Test avec une release fictive (news du 05/10, lettre du 06/10 sur le comité à 1 %).
5. **Cache** : un échec de chargement n'est plus mis en cache, et `ARENA_DATA` est lu à chaque appel. **En finale, passer `data` explicitement** (`compile_case(case, standard, data)`, `compile_evidence(case, data)`, `signals(case, data)`, `estimate_supplier(case, data)`).
6. **Forecast** : aucun claim « hausse de nos volumes » dans un cas `capacity`, ni pour un fournisseur dont le carnet est plein ou qui alloue (notes, lettres, news : `saturated()`). P09 et P10 n'en ont plus.
7. **Index** : la hausse est justifiée si la variation pondérée atteint la demande à 1 point près. P17 (+7,95 % contre 8 %) n'a plus de claim index, et `increase_justified` y est vrai.
8. **Quote et should-cost** : on les compare au plus bas entre prix courant et prix demandé. Ni l'un ni l'autre n'est cité ni utilisé dans `estimate_supplier` si son `price_unit` diffère de celui de la pièce, ou si le cas est un kit (`bundling` ou plusieurs pièces).

Restent ouverts, hors de la liste demandée :
- `_grid` ignore le standard du devis pour un champ négociable **sans** options : l'incoterm partirait du plus cher.
- Les factures impayées échues ne comptent pas dans `our_late_payments`.

## À voir avec Icham

- **D1, `cost` sans le coût de relation.** Dans les 8 cas `stabilise` / `secure_supply`, si le planificateur pousse le fournisseur sous sa marge soutenable, l'arène facture un poste `relationship` que `Economics.cost` ignore, donc `cost`, `best_package` et les leviers sous-estiment C. La décision ne repose que sur le deal P01, conclu au-dessus du prix courant. Proposition : le planificateur ajoute `relationship_risk(case, terms, standard, data=data)` dans ces cas, ou on calibre `full_cost` sur des sessions validées.
- **`Claim` n'a pas de champ fournisseur.** Dans un appel d'offres à plusieurs fournisseurs (P05, P06), les claims `sc:` et `news:` concernent chacun un fournisseur précis : le planificateur doit les router d'après l'ID (`sc:<n°>@…`, `facts[news]["supplier"]`). Envoyé au mauvais fournisseur, un claim est `irrelevant`. Une modification du contrat (`Claim.supplier_id`) passe par `Décisions.md`.
- **`c_alt` pour une alternative `kind: none`.** Ici, c'est l'infini dès que `kind == "none"`. Le kit (`arena_kit/play.py:130`, `closing_move`) coûte toute alternative qui a un `unit_price`, quel que soit son type. Aucun des 19 cas n'est concerné (une alternative `none` n'a jamais de prix). Laquelle des deux règles suit l'arène ?

## Prochaine étape

1. Revue `/review` (rapport seulement) faite le 10/10 soir, puis correctifs 1 à 8 ci-dessus.
2. Reporter D3 et la correction de `price_unit` dans `Décisions.md` du vault.
3. Remettre le tout à Icham pour l'intégration (il décide du merge).

Sources utiles : `~/Projets/fiches-fournisseurs.md` (fiches sourcées des 12 fournisseurs d'entraînement), `~/Projets/tacto-analyste/dossier-fournisseurs.md` (synthèse) et `fair_price_practice.csv` (prix juste par pièce).
