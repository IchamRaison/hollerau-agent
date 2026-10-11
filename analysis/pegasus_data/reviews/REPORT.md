# Renseignement fournisseurs — Pegasus

Mission hors ligne, package v1 daté du 30 septembre 2026. Aucun appel réseau,
aucune clé utilisée, aucun fichier de `kit/` modifié.

## Étape 1 — Lecture et inventaire

Les sept documents prescrits, `arena_kit/data.py` et `arena_kit/cost.py`
ont été lus. Le SQLite comporte les 24 tables annoncées ; `facts.json`
contient 10 356 IDs mais ne couvre pas toutes les colonnes de ces tables.
Les 19 déclencheurs P01–P19 sont présents dans `correspondence/` ; les
fichiers de cas complets sont absents. Les choix de conception et leurs
limites sont consignés dans `QUESTIONS.md`.

Pièges déjà confirmés : prix par `price_unit`, conditions obsolètes dans des
PO, doublon Dralveck `sup:71999`/`sup:70210`, indices décalés, scorecards
glissantes, coûts estimés sans marge. Exemple de fait vérifié :
`cost:310010` = `unit_cost: 132.64`, `confidence_pct: 5`, `price_unit: 1`.

## Étape 2 — Signaux et premier module

Les 208 correspondances, les 39 news et les remarques des devis ont été
explorés. Toutes les clauses structurées figurent textuellement dans les
46 contrats. Les notes administratives (certificats, salons, emballages)
ne deviennent pas des leviers par défaut.

Exemples documentaires, dont les IDs existent dans `facts.json` mais dont
le texte est du contexte (ce n'est pas une mesure numérique vérifiée) :

- `doc:20260824-70110-M1` : tableur de coût ancien ;
  `doc:20260902-70110-M2` : demande de paiement rapide ;
  `doc:20260715-70110-M5` : attente de réciprocité.
- `doc:20260826-70530-M1` : gel des baisses par le siège ;
  `quote:7300003` le confirme dans ses remarques.
- `doc:20260617-70560-M1` et `doc:20260706-70710-M1` :
  matières couvertes ; l'indice spot ne mesure pas le coût réalisé.
- `doc:20260917-70620-M4` et `news:20260619-15` : compte peu stratégique,
  donc une sortie doit rester une option selon le cas.

Le module `intel/dossier.py` fonctionne sur les 46 fournisseurs détaillés.
Première mesure indicative : environ 0,15 s à froid et moins de 0,005 s par
dossier après chargement. Tests systématiques et audit complet restent à faire.
Le prix courant de Brandlhuber est confirmé par `po:4500014428-10` :
`unit_price=126.53`, `price_unit=1`, contre `cost:310010` : `unit_cost=132.64`.
Le préavis donné (`doc:20260911-70110-P01`, `days=51`) est inférieur au
préavis convenu (`ctr:4600070110`, `days=90`) ; cela ne remplace pas la lecture
du prix fixe annuel et du préavis avant fin d'année.

## Étape 3 — Audit complet et livrables

Livrables utilisables :

- `intel/dossier.py` : `supplier_dossier(...)`, `Package`, `agent_brief` ;
  stdlib uniquement, SQLite ouvert en lecture seule, fallback CSV.
- `intel/build.py` : régénération hors ligne de tous les livrables.
- `intel/MAP.md` : les 24 tables, toutes les jointures et les 15 pièges connus.
- `intel/generated/PROFILES.md` et `profiles/*.md` : 46 profils, dont les
  22 fournisseurs explicitement impliqués dans les déclencheurs retrouvés.
- `intel/generated/dossiers.json` : faits + IDs, observations financières,
  dépendances, historique, performance, indices et leviers ;
  `agent_briefs.json` : vues réduites pour l'agent.
- `intel/generated/cases.json` : les 19 déclencheurs, types inférés et
  invitations RFQ explicites ; `RULES.md` : règles transférables sourcées.
- `intel/generated/audit.json` : comptages, colonnes, jointures, concordance
  de valeurs et empreintes ; `metrics.json` : mesure de performance.
- `intel/README.md` : contrat de l'interface, usage et limites.

Audit : **24/24 CSV identiques aux tables SQLite**, **38 relations déclarées
sans référence orpheline**, **51 021 champs directement comparables de
facts.json concordants**, PPM des 1 033 QN recalculés sans écart, rattachement
fournisseur des 280 clauses contrôlé. Les 286 fichiers source ont leur
empreinte SHA-256 dans l'audit ; vérification finale sans modification.
Les 39 événements de conditions sans negotiation_history sont des
ajustements automatiques d'index : ce n'est pas une jointure déclarée ni
une concession commerciale documentée.

Les 495 variations `fc.change_pct` et 5 400 `po.change_pct` sont prises
exactement dans facts.json ; l'algorithme de génération de ces champs
ne fait pas partie de l'audit de reconstruction. Les 225 snapshots de
forecasts absents de facts.json ne sont jamais promus en faits citables.

## Étape 4 — Résultats analytiques et règles transférables

Le module calcule 75 prix ajustés pour des couples supplier-part avec
condition courante. L'erreur should-cost est conservée ; le modèle d'une
autre usine est exclu. Pour six couples, le prix ajusté est inférieur au
coût central applicable ; cela déclenche une lecture cash/marge et une
demande de décomposition, sans affirmer que le coût réel est connu.

Exemple Brandlhuber, **valeurs exactes des sources** :

- `po:4500014428-10` : `unit_price=126.53`, `price_unit=1`.
- `idx:PPI-C241@2026-01` = 98.7 ; `idx:PPI-C241@2026-08` = 105.9.
- `idx:PPI-D351@2026-01` = 127.8 ; `idx:PPI-D351@2026-08` = 131.9.
- `idx:LCI-C@2026-01` = 117.3 ; `idx:LCI-C@2026-06` = 119.6.
- Poids internes `cost_drivers`, clé `part:310010` : acier 0.26,
  électricité 0.06, travail 0.32 ; résiduel fixe 0.36.
- **Calcul dérivé** : prix indexé 129.96730863822904 EUR, environ 129.97.
  `cost:310010` = 132.64, erreur 5 % ; intervalle dérivé 126.008–139.272.
  Le prix indexé est sous le coût central mais à l'intérieur de sa bande.
  La marge nominale estimée au prix courant est −4.83 %, hors ajustements
  paiement/fret/outillage ; ce n'est pas une marge réelle vérifiée.
- L'électricité est **+3.21 % depuis janvier**, mais **−3.72 % sur un an**
  (`idx:PPI-D351@2025-08` = 137.0, `idx:PPI-D351@2026-08` = 131.9).
  Les deux chiffres sont dérivés et vrais sur des fenêtres différentes.
  Éviter « l'énergie baisse donc votre coût baisse depuis le prix courant ».

Nordmark : `part:350011`, prix courant 348.32 (`po:4500014474-10`), ajusté dérivé 363.16,
`cost:350011` = 374.95, erreur 5 %. Lausitz : courant 34.35, ajusté dérivé
35.74, prix courant confirmé par `po:4500014387-10`, `cost:350030` = 37.24, erreur 5 %. Les PO exacts sont dans leurs
profils et les faits sont copiés intégralement dans dossiers.json.
Ces écarts ne prouvent pas une vente sous coût réel ; la limite d'erreur,
les conditions commerciales et le modèle d'usine doivent rester visibles.

Pour Rhönsberg (`part:350040`), `po:4500014438-10` = 316.35 par 100,
`cost:350040` = 304.49 par 100, et prix ajusté dérivé 326.95 par 100.
LCI-C s'arrête avant la condition de juillet : mouvement observé nul,
statut `ok_with_publication_lag`, aucune prévision de salaires inventée.
La couverture cuivre signalée par `doc:20260617-70560-M1` et la clause
`ctr:4600070560#3.2` restent prioritaires pour interpréter ce repère.

Jeu de règles synthétique ; les types peuvent se combiner :

| Situation observée | Leviers à explorer | Preuve documentaire d'exemple |
|---|---|---|
| Cash demandé, protection de marge | Paiement rapide contre concession, marge cash estimée soutenable | `doc:20260802-70130-M1`, `doc:20260902-70110-M2` |
| Capacité libre et intérêt pour la référence client | Charge ferme, regroupement réaliste, durée | `doc:20260723-70250-M1`, `news:20260309-03` |
| Capacité saturée/allocation | Calendrier et allocation contre engagement ferme ; alternative qualifiée | `doc:20260918-70410-P10`, `news:20260822-23` |
| Chiffrage ancien, ouverture aux coûts | Peu d'indices pertinents et décomposition matière/conversion | `doc:20260824-70110-M1`, `doc:20260809-70230-M3` |
| Matières déjà couvertes | Date de fin de couverture, transition, base/extras | `doc:20260706-70710-M1`, `doc:20260617-70560-M1` |
| Gel siège ou comité d'approbation | Conditions non tarifaires et packages approuvables | `doc:20260826-70530-M1`, `doc:20260909-70530-M2` |
| Compte non stratégique et recentrage | Comparer la sortie ; ne pas supposer désir de renouvellement | `doc:20260917-70620-M4`, `news:20260619-15` |
| Scorecard rouge | Plan d'amélioration, PPM réaliste et coût de non-qualité dans C | `sc:70140@2026Q3` : OTD 63.5 %, PPM 2376 ; `sc:70310@2026Q3` : OTD 63.0 %, PPM 4118 |

Les règles automatiques détectent 17 fournisseurs sensibles au cash,
12 avec indices de capacité disponible, six avec capacité contrainte,
cinq avec gel tarifaire, cinq avec matières couvertes et trois avec
désengagement commercial. Ce sont des comptages d'hypothèses détectées,
pas des probabilités calibrées ni des comportements garantis des bots.
La forme juridique ou la catégorie ne suffisent jamais pour décider.

## Étape 5 — Validation et intégration proposée

`python3 -m unittest` : **25 tests passent**. Couverture : chiffres et IDs
exacts pour tous les profils, audit de tables/jointures, fenêtres d'indices,
résiduel fixe, unités 100/1 000, exclusion PO obsolètes, bonne usine
should-cost, ratio CA en bande, doublon historique, fournisseurs long tail,
invités RFQ, absence de paramètres de cas inventés, cache, dates,
fusion de releases synthétiques enfant/voisine, collisions et fallback CSV.

Performance mesurée dans cet environnement : environ **0.128 s à froid**,
**0.0035 s maximum par dossier** après chargement ; largement sous 1 s.
Le dossier complet peut être volumineux : les inputs du retard de paiement
contiennent les dates des factures. Pour le prompt, employer `agent_brief`
sur la pièce concernée. Aucun message à l'arène n'est généré ou envoyé.

La release réelle et les fichiers de cas complets sont absents ; le module
est prêt à fusionner la release extraite localement, mais son contenu réel
n'a pas pu être testé. Les règles textuelles sont des heuristiques de
phrases observées : un signal formulé autrement peut ne pas être extrait.
Le texte documentaire reste disponible pour la lecture par Claude.

Prochaine action proposée à Claude : intégrer `agent_brief` au contexte
de préparation, rapprocher le prix ERP du `buyer.current_unit_price`,
restreindre les citations de devis aux refs/alternatives du cas, calculer C
avec les termes standards et une estimation explicite de la valeur cash,
puis examiner les désaccords entre indices, modèle de coût et propos du
fournisseur. Réexécuter le build après la release déjà extraite sur disque.

## Points à débattre avec Claude

- Q1 : accepter la séparation citables/contexte/calculs, seule manière de
  fournir les finances sans inventer de facts.json.
- Q2 : compléter les 19 déclencheurs avec les vrais cas ; statut hosted,
  objectifs, alternatives et must-haves ne sont pas déductibles hors ligne.
- Q3/Q6 : conserver une base explicite et une fenêtre annuelle séparée ;
  débattre du mouvement observé nul quand LCI précède la condition.
- Q4 : valider la vraie release lorsque disponible, au-delà des fixtures.
- Q5 : choisir comment estimer les taux de cash et la marge soutenable
  dans C ; aucun paramètre économique caché n'est observable directement.

## Tour 2 — Étape 1 : données, traces et critères de citation

Lecture des deux catalogues complets (19 cas practice, dont 10 hosted ; deux
cas sandbox), des quinze exports et du code officiel de coût. Le catalogue
complet remplace la reconstruction partielle ; cette dernière reste conservée
comme `case_triggers.json`. Tous les fichiers source restent en lecture seule.

Les 172 coups et 232 événements de back office sont annotés individuellement
avec positions dans la trace, conditions, raisons déclarées, claims, coûts,
alternatives et échanges internes associés. Les quinze exports ne constituent
que quatorze traces distinctes : les deux runs P01 naïfs sont identiques.
Comptage des contrôles : 11 verified, 30 irrelevant, 15 duplicate, aucun
contradicted. Ces fréquences décrivent ces messages, pas tous les agents.

`agent_brief` contient désormais un catalogue `citable_claims` : phrase anglaise,
refs exactes, valeur scalaire et type d'argument. `max_claims=3` et
`select_claims` sélectionnent sans réutiliser le même ID entre arguments ;
`used_refs` empêche les répétitions des tours précédents. Les refs de devis
rivaux sont filtrées par le cas. Les PO sont 2–8 lignes récentes de même pièce,
prix et unité ; les indices utilisent uniquement une fenêtre annuelle valide.
La vérification linguistique réelle reste hors portée sans API, conformément
à l'obligation hors ligne.

## Tour 2 — Étape 2 : coûts et inversion en cours de validation

Le code officiel est chargé tel quel avec la stdlib, sans écrire de bytecode
dans kit. Chaque option est valorisée contre un package ancre explicite,
puis toutes les combinaisons admissibles sont énumérées et inversées en prix.
Les prix sont vérifiés au centime avec `total_cost` et les must-haves.
La cible 0,99 utilise `C_best + 0,01 × (C_open − C_best)`.

Premiers constats : P04 à 4,96/30 j/24 m coûte 200 292,67 €, contre
198 846,33 € à 12 m. Le prix de secours 4,70 est inférieur au prix négocié :
allonger sans modifier le prix aggrave ici C. P18 possédait au dernier tour
une alternative structurée à 272 611,62 €, soit 3 332,22 € de moins que le
deal signé, avec tous les must-haves satisfaits. Ces constats contestent
respectivement la règle automatique « couvrir deux ans » et le choix de la
seule offre principale.

## Tour 2 — Étape 3 : playbook livré et limites des estimations

`intel/generated/CASE_PLAYBOOK.json` couvre les dix cas hébergés et les douze
profils de demande (trois bidders pour P05). **112 options** sont chiffrées,
avec delta en euros contre une ancre explicite, détail de C et must-haves.
**296 combinaisons admissibles** sont énumérées. Les termes observés avant
snapping sont conservés : notamment le délai initial 52 j de P05 ne fait pas
partie des options de demande et viole le maximum 42 j.

Pour chaque fournisseur : optimum non-prix au prix ancre, égalités de coût,
package cible C_best, package à score ≥0,99, prix d'ouverture exploratoire,
hypothèse de plancher, claims anglais sélectionnés sans doublon et pièges.
L'inversion conserve les deux racines possibles et les scénarios impossibles.
Elle publie aussi la cible sous les conditions non-prix observées pour
séparer une baisse de prix d'un changement de contrat. Les prix sont au
centime ; les deux packages proposés atteignent au moins 0,99 **sous le
modèle publié**, sans garantie que le fournisseur acceptera les conditions.

Les modèles fournisseur sont actifs uniquement pour P01/P02/P03/P10, avec
le terme relationship réellement présent. `supplier_value` officiel est
utilisé ; pas de modèle cash ajouté aux autres catégories.

| Cas | Coût complet retenu €/unité | Taux cash estimé | Justification et limite |
|---|---:|---:|---|
| P01 | 126,008 | 8 % | Bas du should-cost `cost:310010` (132,64 ±5 %), sélectionné ex post : la borne haute compatible avec les deals sans pénalité ne permet pas C_best sous ce taux. |
| P02 | 367,6023 | ≈6,585 % | Taux d'équivalence de paires prix/paiement comparables ; coût inversé depuis relationship observé 112 075,30 €, conditionnel au taux et au standard. Should-cost `cost:350011` =374,95 ±5 %. |
| P03 | 397,44 | ≈4,069 % | Prix 432/30 j et 433,47/60 j : hypothèse de même valeur cash ; coût should-cost `cost:350020` =403,21 ±5 %, plafonné par la pénalité nulle observée. |
| P10 | 24,31 | 8 % | Should-cost `cost:340010` =24,31 ±5 %. Paiement fixé 30 j, donc aucune paire ne permet d'identifier le taux fournisseur. |

Ces chiffres sont des hypothèses ou contraintes calculées, pas des faits
financiers citables. Chaque modèle expose neuf scénarios (bas/centre/haut
should-cost × taux 4/8/16 %). Les estimations fondées sur les paires de devis
supposent l'équivalence cash ; une concession commerciale peut aussi expliquer
leur écart. Le coût calibré et le coût should-cost non calibré sont tous deux
publiés : sur P02 le modèle brut dépasse le deal de 67 318,43 €. Reproduire
le résultat après calibration ne constitue pas une validation prédictive.

## Tour 2 — Étape 4 : constats transférables, avec preuves

- **P01** : les deux replays naïfs concluent à 135,40/60 j et score 0,5828 ;
  les trois packages du run `542fa1f8d903e14c` obtiennent 135,80/30 j et
  score 0,3961. La sélection laissée au fournisseur dégrade C. Le préavis 51 j
  (`doc:20260911-70110-P01` + `ctr:4600070110`) est vérifié, sans remise
  isolable. Aucune final_offer dans ces trois traces.
- **P02** : PPM 273 (`sc:70510@2026Q3`) et préavis 109 j sont vérifiés mais
  déclarés sans effet sur le calcul. Le package avec clause cuivre accompagne
  la baisse. Final_offer au tour 4. Prix bas et pénalité relationship élevée
  montrent pourquoi viser uniquement le prix peut nuire.
- **P03** : forecast +10,3 % (`fc:350020@2026-09`) déclaré pris en compte,
  OTD 84,6 % déclaré sans effet. Agreed au tour 2, puis réaffirmation des anciens
  termes après de nouvelles demandes. L'offre 433,47/60 j était moins chère
  en C de 12 915,60 € que le deal 432/30 j, sous le taux d'équivalence estimé.
- **P04** : timeout, puis final_offer tour 2 sans baisse. C_deal=C_open,
  score 0. Passer de 12 m à 24 m au même prix aggrave C de 1 446,34 € : le fallback
  est moins cher. À12 m/90 j, 4,91 € donne C 196 530,33 €, compatible avec ≥0,99
  selon les standards observés. La durée courte n'est donc pas l'erreur unique.
- **P05** : deux bidders laissés mourir après trois timeouts ; l'autre passe
  en final_offer tour 4 puis sort au tour 5, sans acceptation. Des packages
  satisfaisant le maximum 42 j étaient présents. DAP est fixé par le cas :
  les incertitudes de complétion concernent ici paiement, délai et PPM.
- **P07** : agreed sur 5,62/60 j/36 m ; rouvrir n'améliore pas le deal.
  L'alternative5,66/90 j coûte136 € de plus, malgré le paiement plus long.
  Le prix est par kit ; aucune somme opportuniste des prix des pièces.
- **P08** : OTD 88 % et devis rival6,06 € vérifiés, déclarés sans effet.
  Final_offer tour 3. Clause et durée accompagnent les mouvements ; la variante
  technique évoquée n'est pas une term sheet ferme.
- **P10** : forecast +10,1 % et OTD 79,5 % vérifiés, déclarés sans effet.
  Couvrir le besoin avec 23 400/an et délai42 j améliore C malgré la hausse
  du prix initial. Final_offer tour 2 ; l'alternative36 m a le même C que24 m.
- **P11** : PPM 2376 (`sc:70140@2026Q3`) déclaré pris en compte ; ppm 300
  obtenu au tour 1 sans remise, puis agreed tour 3 à 46,70/cb0. Paiement 60 j et
  volume 15 900 sont fixes : le cash rapide évoqué ne constitue pas un levier
  autorisé dans les feuilles de ce cas. La remise ne peut pas être attribuée
  au seul volume, déjà fixé.
- **P18** : OTD 81 % vérifié, déclaré sans effet ; final_offer tour 2.
  L'alternative finale5,70/60 j/36 m/db5, disponible au moment de la décision,
  était moins chère de 3 332,22 € que le package principal accepté.
- **D02** : C1 reste figé après agreed dans un run ; final_offer tours4/5
  dans les autres. J1 relancé au tour 3 donne immédiatement final_offer et
  annonce une annexe de coûts, alors que C1 n'expose qu'une part matière.
  L'alternative C1 à 45 j viole le maximum 42 j. Plusieurs textes contredisent
  les conditions structurées : seules ces dernières font foi.

Sources exactes et tous les indices de trace/back office :
`intel/generated/SESSION_ANALYSIS.json`, les quinze fichiers dans
`intel/generated/sessions/` et leur synthèse `intel/generated/LESSONS.md`.
Les échanges routés et annonces d'annexes sont préservés ; leurs chiffres
masqués et le contenu PDF/XLSX absent ne sont jamais inventés.

## Tour 2 — Étape 5 : validation et usage

`python3 -m unittest -v` : **45 tests passent** (25 anciens + 20 nouveaux).
Contrôles : faits exacts, pertinence des pièces et fournisseurs, fenêtres idx,
PO homogènes, devis autorisés, absence de doublons dans les trois arguments,
chaque option et chaque combinaison, prix au centime et score≥0,99 sous
hypothèses, must-haves, non-monotonie, cas impossibles, coût des dates/durées,
pénalité relationnelle, équivalences cash, tous les coups/échanges conservés,
déduplication et occasion finale P18. Les quatorze deals sont reproduits au
centime avec les modèles conditionnels ; P05 n'a pas de deal à reproduire.

Build des 46 dossiers rafraîchi : environ 0,130 s à froid et 0,0036 s maximum
par dossier chargé. Code stdlib, entièrement hors ligne ; kit et arena-data
restent en lecture seule. Génération : `python3 -m intel.build`, puis
`python3 -m intel.round2`. Voir `intel/README.md` pour l'intégration de
`agent_brief(..., case=..., max_claims=3, used_refs=...)` et `select_claims`.
Les sections précédentes décrivent le tour 1 : les catalogues autrefois
absents sont désormais fournis et intégrés.

## Points à débattre avec Claude

1. **Contre-exemple prouvé** : corriger automatiquement P04 en 24 m augmente
   C ; choisir durée et prix ensemble, en tenant compte du fallback.
2. **Reconstruction non unique** : C_best ne révèle ni un package unique,
   ni un plancher de réserve. En RFQ il inclut aussi le choix du bidder ;
   les cibles individuelles ne prouvent pas leur acceptabilité chez chacun.
3. **Hypothèses ouvertes** : standards PDF absents, taux d'équivalence et
   coût complet estimés. P01 choisit un scénario compatible ex post ; cela
   ne prédit pas les paramètres des fournisseurs inconnus de la finale.
4. **Ouverture à tester** : les 3 % sous cible sont un choix exploratoire,
   pas une règle apprise. Comparer des politiques en pratique via la boucle
   de Claude avant d'en tirer une cadence universelle de concessions.
5. **Prochain tour proposé** : intégrer les citations filtrées et le tri de
   toutes les offres/alternatives par C, corriger les horloges RFQ et tester
   les packages complets proposés. Remplacer les standards estimés par les
   annexes réelles, puis réévaluer après la release locale. Aucun appel API
   ni message à un tiers n'a été effectué ici.

## Tour 3 — Étape 1 : revue et premier blocage reproduit

Les cinq modules de l'agent, son init, le SDK public de coût/documents/player,
le contrat API et les quinze traces ont été lus. Les sources de revue sont
chargées en mémoire avec un client réseau interdit, sans écrire dans la copie.
Les choix de périmètre sont consignés dans QUESTIONS.md, section Tour 3.

Défaut critique réel : l'ouverture de P05/70240 (lead52>42), P10
(volume19890<22230) et P11 (ppm6400>1500) laisse zéro offre admissible.
`c_s=inf` puis `SCHEDULE[0]*inf=NaN`. `price_for` ne détecte pas NaN et
renvoie sa borne haute. Le replay génère respectivement 363,90 €, 373,60 €
et 478,60 €, soit dix fois les prix de secours. Preuve reproduite avec le
code original, les cas et les messages réellement enregistrés.

Autres défauts en cours de reproduction : relationship omis ; solveur sans
signal d'infaisabilité ; clôture cross-thread contre une offre en remplacement ;
fin prématurée après une erreur close ; fermeture proche du cap qui revient
au helper SDK ignorant les alternatives. Aucun quota ni appel API consommé.

## Tour 3 — Étape 2 : défauts démontrés et intégration proposée

La revue est terminée. [Le rapport détaillé](intel/generated/ROUND3_REVIEW.md)
contient la matrice des défauts, les constats positifs, les risques statiques,
les axes gain/effort/risque et le plan des dix sessions. Les reproductions
sont dans `intel/test_review.py` et [les preuves JSON](intel/generated/ROUND3_REVIEW.json).
La commande `python3 -m intel.test_review --original` échoue intentionnellement
sur **22 invariants** ; les mêmes 22 passent sur les modules proposés.
Les deux courses de clôture utilisent des barrières déterministes, pas une
supposition fondée sur le hasard du scheduling. L'erreur stale est 422,
conformément au contrat API, et une session encore ouverte n'est pas un résultat.

Les [fichiers proposés](pegasus-review/proposed/) et
[PATCH_PROPOSALS.md](pegasus-review/PATCH_PROPOSALS.md) livrent une intégration
concrète : `CASE_PLAYBOOK.cases` et modèles ex post uniquement en practice,
`agent_brief.citable_claims` filtrés et faits privés pour fournisseurs inconnus,
ledger des citations repris/confirmé sur ACK, coûts avec relationship,
inversion non monotone et budget infaisable explicite. Le player draine les
envois engagés, recalcule le meilleur ID/alternative puis clôture hors verrou ;
il rafraîchit les vrais messages sur 409/422 et ne cache pas un close rejeté.
La CLI proposée exige des IDs practice avant toute initialisation de client.

Le module original supporte déjà les `index_clause` dict, les alternatives
à la clôture normale et le choix de durée par C ; aucune correction imaginaire
sur ces points. Le coût officiel n'applique pas la division ERP par price_unit :
il est conservé tel quel, avec libellé « per price unit » dans les citations.

## Tour 3 — Étape 3 : replay, simulateur et validation terminés

[Le replay](intel/generated/ROUND3_REPLAY.json) traite les **89 messages
fournisseur des quinze exports**, soit 172 événements tous acteurs. Original :
18 packages à prix >125 % de l'ouverture, sur six décisions, dont D02/C1
dans trois exports. Proposition : zéro ; aucun package invalide, prix non fini
ou exception sur ces états. Le code corrigé ne fait plus NaN après une
ouverture inadmissible. Ces constats ne sont pas des scores contrefactuels :
les fournisseurs ont répondu à d'autres propositions. Les PDF absents sont
des fixtures texte avec provenance, parfois complétées depuis le résultat.

[Le fournisseur synthétique](intel/generated/ROUND3_SYNTHETIC.json) teste
plancher, décroissance des concessions, final après N et 90 j gratuits/facturés.
Les quatre épisodes ordinaires donnent les mêmes scores synthétiques dans
l'original et la proposition ; l'ouverture must-have invalide passe de 0,571
à 0,857. La variante sans relance agreed perdait des concessions ; la relance
unique est donc conservée, avec contrôle de faisabilité. Ces valeurs ne
mesurent pas la qualité sur l'hébergement et ne garantissent jamais 0,99.

Validation reproductible : `python3 -m unittest discover -s intel -t . -v`
réussit : **99 tests, dont 22 échecs attendus de l’original et 77 succès** ;
[sortie complète](intel/generated/ROUND3_TEST_RESULTS.txt). Les
22 défauts de l'original y sont des échecs attendus, pas des corrections
appliquées à la copie. [Sortie brute dédiée](intel/generated/ROUND3_ORIGINAL_FAILURES.txt)
pour les échecs sans expectedFailure. Le builder `python3 -m intel.review_round3`
régénère preuves, replay, simulations et diff, avec empreintes des sources.
Aucun fichier de kit, arena-data ou pegasus-review/pegasus n'a été modifié.
Aucun appel API, installation ou quota consommé. Les nouveaux scores sandbox
D01/D02 annoncés restent déclaratifs : leurs exports ne sont pas présents.

Le plan propose P11, P10, P05, P02, P18, P01, P03 et P08 ; deux sessions en
réserve pour confirmer les correctifs, sinon P04/P07. Les budgets 0,99 sont
ceux du playbook practice, et ne passent pas en finale. Arrêter les démarrages
au premier défaut critique pour corriger hors ligne ; coordonner le journal
de réservation à quatre avant toute consommation des dix sessions.

## Points à débattre avec Claude — Tour 3

1. **Architecture à corriger** : un worker par bidder est utile, mais un
   verrou de décision ne protège pas les requêtes déjà en cours. Accepter
   sur un autre fil puis mettre done avant le succès est dangereux, preuves
   `inflight_close`/`close_retry`. Relire le drainage et la reprise proposés.
2. **Coût relationnel** : adopter l'estimation explicite et l'inversion non
   monotone ; une borne optimiste sans modèle ne suffit pas à garantir le
   choix en finale. L'alternative demande aussi son propre modèle, si disponible.
3. **Temps de finale** : la marge proposée 210 s conserve le timeout SDK180,
   mais peut coûter des tours et ne garantit pas tous les téléchargements.
   Mesurer sur l'hébergement avant de la considérer validée.
4. **Stratégie** : garder la relance agreed unique, tester une cadence par
   type de cas, et laisser la relance finale désactivée sans contrepartie
   nouvelle. Les traces ne révèlent ni plancher certain ni politique optimale.
5. **Prochain tour** : intégrer les corrections revues, convenir du journal
   de quota, puis exécuter le plan gradué ; fournir les nouvelles traces
   D01/D02 et les annexes pour comparer coûts, citations, latences et scores.

## Tour 4 — Étape 1 : lecture de la version actuelle et choix de portage

ROUND4 et les huit modules actuels ont été lus, ainsi que les propositions et
les 22 invariants du tour 3. Les sources `pegasus-current/pegasus/` resteront
intactes ; les fichiers complets seront livrés dans `proposed/pegasus/`.
Le portage conserve `offered()`, l'exclusion busy, la garde c_s infini,
le plafond ask, les variables PEGASUS_* et bench.py. Le drainage bloquant
est abandonné conformément au retour sandbox D02 ; aucune stratégie RFQ
nouvelle n'est engagée. Les choix sont consignés dans Q17–Q19.
Les dossiers et signaux seront disponibles en finale pour tous les IDs du
package, avec cibles de score et calibrations limitées à practice.

## Tour 4 — Étape 2 : portage et intégration finale opérationnels

Les fichiers complets proposés sont en place : coût officiel avec modèle
relationship, solveur à deux branches borné par ask, préfiltrage de grille,
standards PDF, classement rafraîchi et toutes les alternatives à la clôture.
Le pont intel conserve les cibles et modèles ex post uniquement en practice.
Il charge les dossiers et signaux dans tous les sets, filtre les pièces,
indices, pays et unités, puis revérifie les valeurs contre les faits du cas.
Le package contient 447 fiches fournisseur, dont 71999 alias de 70210 ; le
contrôle couvre chaque fiche, même sans renseignement enrichi. Les signaux
absents restent absents : rien n'est inventé pour les fiches peu documentées.

Le player réserve les requêtes dans un contrôleur sérialisé, puis effectue
les I/O dans des workers indépendants. Il accepte immédiatement une offre
d'un fil sans requête, sans attendre ni les envois ni les annexes d'un autre
fil. Les tests à barrières vérifient close et retour du résultat pendant que
la réponse ou l'annexe adverse restent bloquées. Un 409/422 de clôture
recharge les vrais messages, restaure les citations et redécide ; trois
rejets restent une erreur explicite. Les appels HTTP gardent le timeout SDK.

Les 22 régressions adaptées passent ; 18 vérifications d'intégration
supplémentaires passent également. La relance agreed reste unique ; même
avec l'option activée, une relance final_offer nécessite un package proposant
un paiement plus rapide ou un engagement volume/durée nouveau et chiffré.
Les réglages PEGASUS_* existants et bench.py sont conservés. La validation
complète, le replay et les notes de copie/sandbox suivent. Aucun réseau utilisé.

## Tour 4 — Étape 3 : livraison et validation terminées

Livraison : neuf modules complets dans
[`pegasus-current/proposed/pegasus/`](pegasus-current/proposed/pegasus/),
les deux dépendances intel de production dans `proposed/intel/`, et un
[diff sur la version actuelle](pegasus-current/proposed/pegasus.patch).
[`PORT_NOTES.md`](pegasus-current/PORT_NOTES.md) liste précisément chaque
changement, les paramètres, la copie et les vérifications sandbox de Claude.
Les fichiers `bench.py`, `fetch_sessions.py` et `__init__.py` sont identiques
aux sources actuelles ; ces sources sont intégralement inchangées. Le diff
a passé `git apply --check -p0` sur une copie temporaire de la source actuelle.

Validation finale : **42 tests propres au portage réussis**, dont les 22
régressions demandées et 20 contrôles supplémentaires, aucun expectedFailure.
[Sortie dédiée](intel/generated/ROUND4_PORT_TEST_RESULTS.txt).
La suite complète réussit : **141 tests, 119 succès, 22 échecs attendus de
l'ancien original du tour 3** ; [sortie](intel/generated/ROUND4_TEST_RESULTS.txt).
Le harness accepte maintenant un chemin source explicite ; son comportement
antérieur reste inchangé et le client réseau reste interdit.

[Le builder](intel/review_round4.py) génère
[preuves et empreintes](intel/generated/ROUND4_BUILD_RESULTS.json) et
[replay comparé](intel/generated/ROUND4_REPLAY.json). Les 89 messages
fournisseur des quinze exports donnent zéro exception, prix non fini ou
package invalide sur les deux versions. La copie actuelle avait déjà corrigé
les surenchères observées au tour 3 ; aucun gain fictif sur ce point n'est
attribué au portage. Les actions passent de 20 à 37, surtout avec relationship,
mais ces réponses historiques ne prouvent aucun score contrefactuel.
Deux propositions de P03 relaxent explicitement un budget sous le minimum
estimé : C demandé 3 870 272,66 puis 3 896 151,72 €, C effectif 3 964 566,23 €,
prix 420,33 €, sous le plafond fournisseur. Trois actions ultérieures gardent
ce diagnostic ; le compteur brut de cinq n'est pas cinq nouvelles relaxations.

Le contrôle final couvre 447 fiches/446 fournisseurs canoniques. La production
n'attend pas une liste des 40 fournisseurs finaux et accepte les nouvelles
combinaisons sans emprunter le fair-price d'une autre pièce. Cash, gel,
capacité et couvertures des matières sont branchés, avec leurs sources et
confidence. Après chargement du package, les 447 briefs ont pris 0,183 s
au total, maximum 0,0034 s par fiche lors du dernier build local.
Ces durées ne mesurent ni le fournisseur ni l'extraction des PDF hébergés.

Aucun appel réseau, session practice/sandbox/final, installation ou message
à un tiers n'a été effectué. Aucun code du kit, aucune donnée arena ou copie
source des deux tours n'a été modifié. Le simulateur et la stratégie RFQ
restent à Fable. Les scores annoncés dans ROUND4 restent des informations
fournies par Claude/Tacto, sans nouvelle vérification réseau ici.

## Points à débattre avec Claude — Tour 4

1. **Timing validé localement seulement** : tests à barrières prouvent close,
   retour et activité du fil B pendant le blocage A. Mesurer sur sandbox les
   requêtes, annexes et resync ; régler `PEGASUS_CLOSE_MARGIN_S` avant finale.
2. **Relationship** : revoir hypothèse should-cost/8 %, pays et unités, puis
   comparer P02/P03 aux résultats réels. Un modèle absent reste explicitement
   une borne optimiste ; l'alternative n'a pas le modèle du fournisseur courant.
3. **Citations finales** : les dossiers sont valables pour les fournisseurs
   du package, mais la pertinence linguistique des nouveaux messages et PDF
   exige les retours hébergés ; inspecter contradicted/irrelevant/duplicate.
4. **Prochain tour** : Claude copie les fichiers, joue d'abord la référence
   D01/D02 aux réglages validés 0,80/0,94, puis fournit les traces/annexes et
   latences. Ensuite seulement le plan practice coordonné, sans sessions
   automatiques supplémentaires sur un moteur déterministe.

## Tour 5 — Étape 1 : résultats A/B et régression reconnue

ROUND5, la nouvelle copie `pegasus-current/latest/` et les quatre exports
sandbox-ab ont été lus. Les scores sont désormais observés dans les traces,
plus déclaratifs : A/B D01 0,968545/0,919901 ; D02 0,723213/0,219747.
La conformité technique du tour 4 n'était pas une preuve de bonne stratégie.
L'acceptation parmi les seuls fils idle peut choisir le fournisseur plus
cher ; cette politique ne doit pas remplacer le nouveau wait de Claude.

Premier écart D01 au deuxième e-mail : B retire le package à 30 jours et
ajoute une date février ; le fournisseur passe à 45 jours et concède moins.
Sur D02, B n'offre pas 14 jours et n'envoie aucune citation rivale, subit un
timeout J1/r2, puis accepte C1/16,70 alors que J1/15,40 coûte moins en C.
Les PDF et timestamps absents imposent de séparer cause de code reproductible
et détails de transport non identifiables. La greffe visera latest, sans
remplacer son player, sa politique RFQ ou son pas minimum visible.

## Tour 5 — Étape 2 : explication coup par coup et choix de la greffe

Le [rapport détaillé](pegasus-current/ROUND5_REVIEW.md) contient tous les
packages D01, tous les coups D02 avec leurs indices JSON, les claims verified,
les raisons back office, les coûts et les mécanismes reproduits.
D01 perd 1 954,83 € : +4 004,38 € d'achat, compensés par −1 309,35 € de
paiement et −740,20 € de relationship réel. Aucun modèle relationship n'est
actif dans B/D01 ; le reclassement et l'absence de détection Zahlungsziel
retirent le paiement 30 jours à r2. Chaque ablation, regex A ou classement
figé, le restaure à réponse r1 historique identique.

D02 perd 28 978,13 € : 13 890,13 € de termes J1 moins favorables et 15 088 €
d'attribution C1 au lieu de la feuille J1 réellement exportée. Le paiement
14 jours disparaît chez B ; la feuille rivale C1-0 est filtrée comme non
attribuable alors que A obtient un claim verified et une concession interne
explicitement liée à ce rival. B a un timeout J1/r2, puis sa politique
excluant busy reproduit l'acceptation de C1. Busy vide, B choisirait J1.
Les PDF sans octets et l'absence de timestamps empêchent d'identifier la
latence du timeout et le moment exact de publication locale ; le rapport
ne transforme pas les hypothèses d'hydratation en faits mesurés.

A reste critiqué : relationship réel de 833,90 € ignoré sur D01, variantes
C1 inutilement rapides, deux questions J1 sans amélioration du prix,
pas15 % pouvant devenir quelques cents. Le risque wait/60 s, closing_move
proche cap ignorant alternatives/modèle/busy, fenêtres de réservation et
I/O sous verrou sont des risques de code séparés des incidents observés.
Aucun timeout A n'est présent dans les deux exports. La plainte « one cent »
rapportée par Claude n'apparaît pas dans ces quatre parties.

## Tour 5 — Étape 3 : livraison et validation terminées

La [greffe complète prête à copier](pegasus-current/latest-proposed/) comporte
12 modules pegasus et 2 modules intel ; seuls agent/economics/claims sont
modifiés depuis latest. Trois sidecars ajoutent Intelligence, sélection de
claims et inversion relationship ; les deux dépendances intel sont des copies
identiques. [Notes précises de portage](pegasus-current/LATEST_PORT_NOTES.md),
[patch applicable](pegasus-current/latest-proposed/pegasus.patch).
Le player, guard, CLI, bench, fetch et init sont identiques au byte à latest.
_done, wait, CASH_RE, MIN_STEP et classement à l'ouverture sont conservés.

Le modèle actif propage le coût officiel jusqu'à la clôture de l'agent,
utilise le standard cash du devis actualisé avant calcul, traite les deux
branches de C(P) et le plafond ask au centime. Les modèles absents sont des
bornes optimistes déclarées, sans calibrage DEMO sur les scores. Un budget
infaisable produit une question et un diagnostic, sans relaxation silencieuse.
Les cibles/calibrages ex post restent practice-only. Le closing_move du SDK
proche cap conserve sa limite : il ignore le nouveau modèle.

Les briefs couvrent les 447 fiches/446 fournisseurs canoniques dans tous
les sets. Cash/gel enrichissent les flags ; capacité/matières couvertes
ajoutent des questions sourcées. Les citable_claims revérifient faits privés,
pièce, unité, pays et fraîcheur, limitent les usages et passent le guard
existant. Les numéros ERP de pièces ne sont plus lus comme des mesures dans
leurs phrases. Les historiques de prix supérieurs au prix demandé sont
écartés. Aucun nouveau cycle ACK/rollback n'est attribué au player inchangé.

[La preuve de compatibilité](intel/generated/ROUND5_COMPATIBILITY.json)
compare **28 décisions complètes, 78 packages et 10 clôtures avec états busy** :
zéro différence A→greffe. Le harness reproduit aussi tous les packages
numériques enregistrés A/A et B/B, avec fixtures de standards déclarées.
A→greffe conserve prix et arrondis hors modèle sur toutes les structures
légales D01/D02 testées ; les DEMO absents ne chargent pas le package intel.
La preuve est comportementale sur ces inputs, sans nouveau score hébergé
ni garantie de timings identiques. Les réponses restent historiques.

Les **22 tests du tour 5 passent**. La suite complète réussit : **163 tests,
141 succès, 22 échecs attendus de l'ancien original du tour 3** ;
[sortie](intel/generated/ROUND5_TEST_RESULTS.txt).
Le patch passe git apply --check puis l'application dans une copie temporaire,
qui produit exactement les 14 modules livrés. Les empreintes des neuf fichiers
latest et les comparaisons avec HEAD confirment toutes les sources inchangées,
y compris ancien portage B, kit et arena-data. Le JSON historique régénéré
par la suite ne variait qu'en ordre de clés et a été conservé byte pour byte.
[Validation du patch, des empreintes et des liens](intel/generated/ROUND5_VALIDATION.json).

Aucun appel réseau, installation, session ou message tiers n'a été effectué.
Les scores officiels A/B sont lus dans les exports ; aucun score du patch
ni séparation chiffrée des effets cash/claims/timeout n'est inventé.

## Points à débattre avec Claude — Tour 5

1. **La politique busy du tour 4 est invalidée économiquement.** Conserver
   wait de latest ; instrumenter clocks, reçu/publié/hydraté et réservation,
   puis borner l'attente sans attribuer prématurément le lot plus cher.
2. **La greffe conserve les décisions DEMO, pas des timings non exportés.**
   Claude peut mesurer D01/D02 à 0,80/0,94/MIN_STEP0,15 avant copie finale ;
   aucune session n'est demandée ni démarrée automatiquement dans ce tour.
3. **Relationship reste une estimation.** Vérifier standard PDF, should-cost,
   unité/pays et sensibilité cash4/8/16 % sur fournisseurs connus ; décider
   séparément comment négocier un ancrage inférieur au minimum réalisable.
4. **Finale : mesurer les claims et le chemin proche cap.** Le filtre et le
   guard sont contrôlés hors ligne ; leurs résultats linguistiques API et le
   modèle ignoré par closing_move exigent une vérification hébergée ultérieure.
5. **Ablations distinctes.** Tester une variante C1 lead35 et le maintien J1
   sans perdre paiement rapide/citation rivale. Le patch complet B ne doit
   plus être la base de ces essais ; latest-proposed est la greffe retenue.

## Tour 6 — Étape 1 : traces et copie de référence

ROUND6 a été lu. Les dernières sessions sont sélectionnées par
summary.created_at, et non par nom ou mtime. P08/f55ad06be81419b1 vaut
0,150821 ; P11/c168282558ca273e vaut 0,314395. Les anciens P08/P11 servent
à comparer les comportements observés, pas à prédire les nouveaux scores.
Le snapshot initial latest-r6 conserve les deux défauts décrits : classement
au prix d'ouverture et promesse de paiement sans vérifier negotiable.
Une copie de référence de ses onze modules est conservée dans
intel/round6-baseline, avec empreintes. La revue/replay n'écrit pas dans
latest-r6 ; la disponibilité des correctifs de Claude a été demandée pendant
que l'analyse indépendante se poursuit. Aucun appel réseau.

## Tour 6 — Étape 2 : diagnostic confirmé, avec limites causales

P08 : les neuf packages des trois messages récents couvrent douze mois.
Le classement s'inverse à 5,93114 €/kg : à 6,05 €, douze mois + fallback
dominent ; à l'ancre 4,84 €, vingt-quatre mois dominent. L'ancienne ancre
surestime le C minimal de 102 750,56 €. Les 542 256 € non couverts ne sont
pas un gain gratuit : à prix final inchangé 5,85 €, passer à vingt-quatre
mois économise seulement 7 640,88 €, soit un score algébrique de 0,194339
contre 0,150821. La dernière alternative 5,76 €/14 jours coûte même
747,02 € de plus que 5,85 €/90 jours. Le choix de clôture était correct.

P11 : les quatre messages promettent un paiement accéléré impossible.
Le fournisseur l'attend explicitement jusque dans sa finale à 48 €.
La causalité chiffrée de cette phrase seule n'est pas identifiable.
Les trois packages à chaque tour gardent cb500 et le même prix ; le ppm
ne coûte alors rien à l'acheteur, mais reste une obligation fournisseur.
Le choix du ppm1500 est donc une information réelle, contrairement au
diagnostic « alternatives sans information ». L'alternative du premier
retour à 47,50 €/cb150 aurait coûté 795 € de moins que la finale ; elle
n'est plus une offre courante à la clôture. L'ancien échange montre que
Kalwisz valorise le moindre chargeback et la confirmation explicite du
volume fixe 15 900/an : après celle-ci il accepte 46,70 €/ppm300/cb0.

Séquence plausible P08 : confirmer 94 800 kg/an sur deux ans, échanger
durée/paiement/clause à C comparable, puis accepter le meilleur C courant.
Séquence plausible P11 : préciser d'emblée les paramètres fixes
60 jours/15 900/an/12 mois/56 jours, puis explorer prix/ppm/chargeback et
répondre à la contre-proposition cb150. Ne pas répéter la demande de coût
après refus, ni transformer une confirmation de volume en nouveau levier.
Ces séquences sont appuyées par les échanges, sans score futur inventé.

P02/P10/P18/P05 n'ont pas l'inversion d'ancre P08. P02 manque plutôt la
confirmation du volume demandé ; P10 demande 35 jours sans gain de coût
acheteur face à 42 et reçoit un surcoût d'heures supplémentaires ; P18
n'explore pas la clause pourtant réclamée ; P05 dépend aussi des timeouts
et des états busy, non reconstruits par le replay des réponses serveur.
L'analyse trouve aussi des changements d'ancre légitimes sur P01/P04.

## Tour 6 — Étape 3 : correctifs rejoués et verdict

Les correctifs reçus sont contrôlés à empreintes constantes : best_at_price
pour l'ancre, best_for_target pour les packages, alternatives à au moins
90 % du prix principal et prose limitée aux leviers négociables.
Le [rejeu complet](intel/generated/ROUND6_REPLAY.json) couvre 29 exports,
179 décisions sur événements fournisseur, puis 51 décisions aux instants
acheteur des dix traces practice récentes. Cas disponibles :
P01/P02/P03/P04/P05/P07/P08/P10/P11/P18 et D01/D02.
Trois exports sandbox récents supplémentaires (D01, D02 à 0,723 et D02
à 0,702) ajoutent 32 décisions : **32 traces, 211 décisions fournisseur**
au total, sans nouvelle erreur ni promesse impossible.
Aucune exception, violation de budget/must-have/options, acceptation
périmée ou promesse de paiement fixe. Les actions finales restent identiques.
133 décisions changent, principalement packages et formulations ; cela
n'est pas une mesure de dégradation ou de gain de score.

P08 ouvre désormais à 4,84 €/90 jours/24 mois. P11 propose cb500 à
37,60 € et cb300 à 37,55 €, et supprime le paiement accéléré impossible.
Tous les packages observés respectent le seuil 90 %. Le seul écart à
l'oracle de prix maximal survient dans une ancienne trace P05 après un
événement sans prix : le plafond ask mémorisé explique cet écart ; il
n'existe pas aux 51 instants acheteur rejoués.

Réserves : P08/P18 proposent encore 36 mois au même C que 24 ; P11 garde
une alternative ppm seule à prix identique avec cb500 ; P10 conserve son
délai de 35 jours ; P18 ne teste toujours pas la clause demandée. Ce sont
des limites de stratégie, sans nouvelle invalidité. Les ancrages P01/P04
changent : leurs réponses futures restent à mesurer. Le modèle relationship
reste absent (écart P02 final 611,74 €, non attribué à ces correctifs).

Les **22 tests du tour 6 passent** (`python3 -m unittest intel.test_round6 -v`),
y compris la conservation de wait en RFQ avec état busy explicite.
Les standards sont des fixtures déclarées ; les réponses demeurent celles
adressées aux messages historiques. Aucun score contrefactuel, réseau ou
session lancée. Sandbox communiqué par l'utilisateur : D01 0,969 inchangé,
D02 0,702, soit −0,021 contre la référence 0,723 du commentaire source.
**Verdict : GO pour dix sessions practice mesurées**, avec suivi séparé
P08/P11, P01/P04, P10 et P18. Aucune garantie de gain de score.

## Tour 7 — Écarts, règles générales et proposition

[La revue détaillée](pegasus-current/ROUND7_REVIEW.md) traite P02/P11/P05/
P07/P18/P10 sur les deux lots et les anciens échanges du kit, avec raisons,
back offices, décomposition du C et contreparties effectivement obtenues.
[Les données et le rejeu](intel/generated/ROUND7_REPLAY.json) conservent les
preuves par fichier et index de trace. Les lots sont triés par created_at.

Écarts lot 2 à C_best : P02 **23 570,80 €**, P11 **50 001,48 €**,
P05 **21 843,17 €**, P07 **29 779,31 €**, P18 **34 807,36 €**.
P10 n'a pas de deal au lot 2 ; l'écart du lot 1 est **264 082,71 €**.
Les sensibilités de termes ne sont pas des concessions gratuites : clause
deadband5 P18 5 652,45 € à même prix ; qualité P11 seulement 715,50 € ;
paiement90 P05 4 081,50 € si le prix restait constant, ce qui n'est pas promis.
P02 et P07 ont déjà les meilleurs termes à prix constant hors relationship.

Les variantes rapides P02/P07/P18 sont moins chères nominalement, mais
plus chères en C : elles ne comblent pas l'écart. Le fournisseur P11 a
effectivement accepté cb0 dans l'ancien kit et baisse après confirmation du
volume ; P18 accepte la famille de clause et ses alternatives montrent un
deadband5. P05 a déjà obtenu les deux étapes de baisse induites par la vraie
concurrence ; répéter après accord ne produit plus de concession. P10 a
un problème d'acceptation d'alternative déjà corrigé par Claude : le renvoi
snappe 54 à 56 jours, ajoute 4 800 € de retard et reste moins cher que le
principal. Aucune acceptation d'identifiant alternatif n'est ajoutée au patch.

Classement ordinal gain attendu × confiance (1–5, pas des probabilités) :
**menus d'échanges pertinents 4×4**, **relance finale avec giveaway réellement
nouveau 3×3**, volume/durée légaux 3×2, breakdown sans plancher 2×2,
modèle de marge après calibration 3×1. Les risques et cas croisés sont
explicités dans la revue ; aucune règle n'emploie les scores ou C_best.

[latest-r7-proposed](pegasus-current/latest-r7-proposed/) livre les deux
premières règles dans agent/economics, et intègre distance de latest-r7b.
Le meilleur prix au C est conservé ; les alternatives peuvent varier plusieurs
champs, les clauses exigées sont reconnues et les paramètres fixes décrits
fidèlement. Le paiement fixe P11 est répondu explicitement ; les engagements
raw material portent kg et le bundle son périmètre complet.
Une relance finale réserve réponse/clôture, ne dépasse pas une fois, saute
RFQ/busy/playbook et une meilleure alternative déjà pricée. Un délai30 inédit
n'est pas nouveau si paiement14 a déjà été proposé ; les structures produites
sont aussi mémorisées pour éviter qu'un replay historique recycle un giveaway.
Budget infaisable avec exigence observée : question, sans fallback qui la relaxe.

Le départage r7b résout ppm1500 et lead42 à prix égal. P01 ouvre déjà en
novembre dans r7 et r7b : à 118,94 < prix courant 126,53, ce choix est
économiquement correct. Des probes de part et d'autre du prix courant vérifient
le recalcul novembre→avril. Le risque se situe au passage de la finale
129,80 > prix courant : 11 137,98 € de gain brut d'un report à prix constant
ignorent le changement de relationship (11 778,11 € au deal), alors que le
résidu officiel à C_best n'est que 715,47 €. Ne pas promettre ce gain brut
ni attribuer 0,995→0,987 à la seule distance. Sandbox 0,979/0,702 est
l'information de l'utilisateur, sans résultat hébergé de notre proposition.

Les autres neuf modules sont conservés ; les originaux r7/r7b et les données
ne sont pas modifiés. Les patches FROM_R7 et FROM_R7B permettent la revue
et l'application sur la base correspondante. PEGASUS_FLOOR reste désactivé.
Le rejeu, les tests et la validation finale sont consignés ci-dessous.

## Tour 7 — Validation finale

**27 tests réussis** (`python3 -m unittest intel.test_round7 -v`). Ils couvrent
les trades qualité/chargeback, les clauses requises et négations, l'absence de
relaxation de budget, l'unité d'engagement, le vrai nouveau giveaway, la relance
unique, les tours restants, busy, les refus et le renvoi d'une alternative avant
acceptation du principal confirmé. Les décisions complètes actuelles P01/P03/
P04 et toutes celles DEMO D01/D02 sont identiques à r7b.

**39 traces / 240 décisions fournisseur**, puis **50 décisions aux instants
acheteur des dix traces lot 2** : zéro exception, violation de budget/options/
must-have, promesse fixe impossible ou nouvelle erreur technique. Aucune
clôture réalisée comparable ne change. La relance P02 à l'instant de clôture
est explicitement censurée faute de réponse enregistrée ; elle propose
CU-NOTATION/deadband3/paiement14 à 358,33 €, calculée sans C_best. Les archives
contiennent aussi des relances P08 et P10, recensées dans le JSON ; aucune
réponse nouvelle n'est simulée. Les écarts à l'oracle de prix sans contraintes
incluent les clauses exigées et giveaways nouveaux : ils ne sont pas cachés
ni interprétés comme une perte de score.

[Validation livrée](intel/generated/ROUND7_VALIDATION.json) : les deux patches
passent git apply --check puis application dans une copie temporaire, qui
reproduit exactement les onze modules proposés. Tous les modules compilent.
Seuls agent/economics changent, les neuf autres sont identiques ; les empreintes
r7/r7b/proposition correspondent au rejeu. git diff --check passe.

**Proposition prête pour essais mesurés**, avec risque explicite de retrait
d'une finale et modèle relationship absent. Aucun appel réseau, installation,
session, message tiers ou gain hébergé revendiqué. REPORT et QUESTIONS sont
mis à jour ; l'analyse de P01 distingue optimum algébrique et risque commercial.

## Tour 9 — Chercher des concessions supplémentaires

[Revue complète](pegasus-current/ROUND9_REVIEW.md) : toutes les parties des
six cas faibles, 11 idées classées par plafond de gain visé × confiance,
lecture seule des trois dépôts de l'utilisateur. Le corpus contient 42 parties
practice, 39 traces distinctes ; les deux parties naïves concernent P01,
aucune trace naïve des six cas faibles n'est présente.

Le prix seul égare : P02 à 344,20/14 j/index donne score 0 avec relationship,
contre 0,502 à 371,92/90 j. P18 cède 0,10 par tour indépendamment des pas
acheteur observés ; P07 reproduit le même +0,22/−0,07. Les échantillons ne
permettent pas d'attribuer causalement la finale au pas, aux feuilles ou au ton.
P05 montre une validation interne avant 30,50→28,77 ; P10 garde un tour de
plus dans la trace LLM à ancre 30, contre une finale immédiate à 25,76 chez
pegasus. Ces associations fondent des expériences, sans prouver leur gain.

[Proposition](pegasus-current/latest-r9-proposed/README.md) : trois règles
générales dans agent.py seulement : validation commerciale dans le contre-mail,
BAFO RFQ avec devis rival réalisable, ancre/menu adaptés à une double pression
volume/délai. Dix autres modules identiques ; aucun ID de cas ni C_best ajouté.
Les trois expériences se désactivent indépendamment ; FINAL_TRADE reste à 0.

**13 tests réussis ; 199 archives / 1 044 décisions par version** : aucune
nouvelle régression technique. Actions de clôture et 199 clôtures au cap
identiques ; six décisions P10 changent de feuilles, 119 messages changent.
[Replay](intel/generated/ROUND9_REPLAY.json) et
[validation](intel/generated/ROUND9_VALIDATION.json) consignent les limites,
empreintes, compilation et application exacte du patch sur une copie temporaire.

Les réponses historiques sont imposées aux deux politiques : aucun gain de
score nouveau n'est démontré. Proposition prête pour essais mesurés ; pas de
validation pour la finale. Aucun appel réseau, nouvelle session, installation,
modification des dépôts externes ou des snapshots de Claude.

## Tour 10 — Lire les réponses et adapter les offres

[Revue complète](pegasus-current/ROUND10_REVIEW.md),
[gold](intel/generated/READER_GOLD.json) et
[métriques](intel/generated/READER_METRICS.json) : 203 archives, 2 859 phrases
exactes, 2 021 formulations normalisées. Toutes les raisons fournisseur,
ouvertures et emails de trace/threads sont couverts. Annotations sémantiques
explicites par Codex, indépendantes des sorties du détecteur ; pas de second
annotateur indépendant. Corpus de développement, pas un test de généralisation.

Repli initial : précision 92,9 %, rappel 35,2 %. Proposition : **99,8 % / 95,5 %**.
Les formulations de cash, volume attribué, stabilité contractuelle, index
obligatoire, délai ferme et données sans effet sont mieux reconnues. Négations,
approbation déjà terminée, limite de paiement et proximité du plancher sont
testées. La citation LLM est vérifiée littéralement sur sa ligne, sans garantir
la justesse du type ; le chemin LLM réel n'est pas évalué.

[Proposition](pegasus-current/latest-r10-proposed/README.md) : seul agent.py et
reader.py changent, onze autres modules identiques. reader.apply pilote les
contraintes d'index/chargeback/volume/durée/délai, le menu de trades sous gel,
la revue commerciale, les arguments réduits et la disposition à clore au
plancher. Un plancher ne fait pas abandonner un trade faisable encore inédit.
Pas de valeur par cas ni C_best ajoutés ; FINAL_TRADE reste désactivé.

**23 tests réussis ; 203 archives / 1 076 décisions par version** : aucune
nouvelle régression technique. Les coûts, must-haves, options et IDs de clôture
sont vérifiés ; les 203 clôtures au cap restent identiques.
[Replay](intel/generated/ROUND10_REPLAY.json) et
[validation](intel/generated/ROUND10_VALIDATION.json) consignent les empreintes,
compilation et application exacte du patch dans une copie temporaire.

Les cinq cas faibles changent aussi sur leur dernière archive : textes/feuilles
P05 8/4, P07 2/2, P18 3/2, P08 4/1, P02 4/1. Ils satisfont donc le critère
pour des essais practice ciblés ultérieurs. Aucun nouveau score n'est démontré
par les anciennes réponses imposées. L'index obligatoire, les engagements
allongés et la disparition du cash déduit de Zahlungsziel modifient réellement
les menus ; les anciens scores D01/D02 ne valident pas cette politique.
Aucun appel réseau ni nouvelle session ; snapshots et données intacts.
