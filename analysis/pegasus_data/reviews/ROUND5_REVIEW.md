# Tour 5 — Régression A/B et greffe sur latest

B régresse réellement : **D01 0,919901 contre 0,968545 ; D02 0,219747 contre 0,723213**.
Sur D01, B remplace la variante à 30 jours par une autre date d'effet dès r2.
Sur D02, B retire le paiement à 14 jours et les citations rivales, perd un round
par timeout, puis choisit C1 malgré une feuille J1 moins coûteuse. Le modèle
relationship n'est actif dans aucune de ces négociations DEMO : il n'explique
pas leur régression. Les tests du tour 4 validaient les invariants de son
implémentation, y compris une politique busy devenue économiquement mauvaise.

## Sources et portée

- [A/D01](../arena-data/sandbox-ab/A-D01-c5683bddd85b6083.json),
  [B/D01](../arena-data/sandbox-ab/B-D01-32b1bb3373a5126b.json).
- [A/D02](../arena-data/sandbox-ab/A-D02-540a2a5b6723bfa3.json),
  [B/D02](../arena-data/sandbox-ab/B-D02-3e8e52aed630ddbd.json).
- A : `latest/`. B : `proposed/pegasus/`, proposition complète du tour 4.
- Chiffres officiels : `session.result.{terms,c_deal,c_open,c_best,score,cost_breakdown}`.
  Coups : `session.result.trace[i]`, **indices JSON à partir de zéro**.
  Raisons internes : `backoffice[i].text`. Fils et timeouts : `threads` et `session.moves`.
- Les paramètres du rejeu sont ANCHOR=0,80, PI_ANCHOR=0,94, MIN_STEP de A=0,15.
  Les autres paramètres conservent leurs valeurs par défaut.

Le statut pertinent est celui de la trace au moment du coup. Les messages
exportés après acceptation peuvent être devenus `agreed`. Aucune horloge de
transport/publication n'est exportée. Les annexes sont identifiées, mais les
PDF/XLSX n'ont ni texte ni octets (`content_b64` nul). Le harness fournit donc
une **fixture texte déclarée** pour les standards : F1 30 j/FCA/650 ppm,
J1 30 j/28 j/EXW/1100 ppm, C1 45 j/45 j/EXW/2600 ppm. Il conserve les vrais
messages et termes de la trace. Les coûts RFQ retrouvés au centime et la
reproduction de tous les packages corroborent cette fixture ; ce n'est pas
une extraction des PDF absents.

[Analyse JSON](../intel/generated/ROUND5_AB_ANALYSIS.json),
[comparaison et ablations](../intel/generated/ROUND5_COMPATIBILITY.json),
[builder reproductible](../intel/review_round5.py).
Les réponses historiques sont imposées au rejeu : aucune nouvelle réponse
fournisseur, session ou mesure de score du patch n'est produite.

## D01 — Le package utile disparaît à r2

Tous les packages ci-dessous engagent 24 mois. `avril` signifie 2027-04-01,
`février` 2027-02-01. Notation : prix EUR / délai de paiement en jours / date.
L'ouverture est identique : **52,90 / 30 / 2026-12-01**, contrat 12 mois.

| Round ; indices buyer/réponse | Packages A | Packages B | Réponse A → B |
|---|---|---|---|
| r1 ; 1/2 | 45,68/60/avril ; 45,49/45/avril ; 45,31/30/avril | identiques | 51,80/30/avril → identique |
| r2 ; 3/4 | 47,11/60/avril ; 46,92/45/avril ; **46,74/30/avril** | 47,11/60/avril ; 46,92/45/avril ; **47,24/60/février** | **51,10/30 → 51,30/45**, avril |
| r3 ; 5/6 | 47,89/60/avril ; 47,70/45/avril ; 47,51/30/avril | 47,89/60/avril ; 47,70/45/avril ; 47,95/60/février | 50,50/30 → 51,00/45, avril |
| r4 ; 7/8 | 48,39/60/avril ; 48,20/45/avril ; 48,01/30/avril | 48,55/60/avril ; 48,35/45/avril ; 48,55/60/février | 50,10/30 → 50,70/45, avril |
| r5 ; 9/10 | 48,71/60/avril ; 48,52/45/avril ; 48,32/30/avril | 48,96/60/avril ; 48,77/45/avril ; 48,93/60/février | **final 49,80/30 → final 50,40/45**, avril |
| clôture ; 11 | accepte F1-5 | accepte F1-5 | même round, termes différents |

A classe les structures à l'ouverture et garde ce classement. B recalcule
le classement à chaque réponse. Le départage « coût voisin/proximité des
termes du fournisseur » place alors février parmi les trois variantes et
évince 30 jours. L'expression cash de B ne comprend plus `Zahlungsziel` ; son
flag cash reste faux et ne réinsère pas la variante rapide. A conserve cette
expression et le classement initial. Il ne s'agit donc pas d'une ouverture
B trop agressive : **les trois prix et la première réponse sont identiques**.

Les deux ablations locales sont discriminantes : garder le classement initial
**ou** restaurer l'expression cash de A remet 30 jours à r2, à réponse r1
historique identique. Elles prouvent le mécanisme de sélection des packages,
pas la future réponse ni un score. À partir de r4, les standing costs et donc
les budgets de concession ont également divergé. B n'a pas le MIN_STEP récent
et les textes diffèrent ; ces facteurs ne sont pas isolables comme gains de
score à partir de ces seules parties. Le back office F1 donne seulement
« counter » à chaque round, sans causalité linguistique plus précise.

| Composante de C final | A | B | B − A |
|---|---:|---:|---:|
| Achat avec date d'effet | 396 808,77 € | 400 813,15 € | +4 004,38 € |
| Paiement | 2 645,39 € | 1 336,04 € | −1 309,35 € |
| Fret | 9 600,00 € | 9 600,00 € | 0 € |
| Relationship réel exporté | 833,90 € | 93,70 € | −740,20 € |
| **Total** | **409 888,06 €** | **411 842,89 €** | **+1 954,83 €** |

Avec C_open=448 810,67 et C_best=408 623,99, ces coûts redonnent exactement
les scores exportés. Le paiement plus long et la relation moins pénalisée
compensent une partie du surprix ; ils ne compensent pas 4 004,38 € d'achat.
DEMO-F1 n'existe pas dans le package et le cas fourni n'a pas de fait privé
unit_cost exploitable : B annonce `unknown_optimistic_lower_bound`, fournisseur
modélisé nul. Attribuer cette perte à notre solveur relationship serait faux.

## D02 — Trois leviers perdus, puis la mauvaise attribution

Les tables en annexe conservent **chaque coup dans l'ordre du serveur**.
Notation RFQ : prix / paiement / lead time / incoterm.

1. **Ouvertures identiques, trace[0:2].** J1 : 17,10/30/28, incoterm absent ;
   C1 : 16,00/45/EXW, lead time absent. Avec son standard 45 jours, C1 viole
   initialement le must-have lead≤42. Son prix reste un levier commercial
   vérifiable, même si cette feuille n'est pas immédiatement attribuable.
2. **J1/r1, trace[2:4].** A propose 13,54/14/28/DAP parmi ses trois packages
   et cite `offer:DEMO-C1-0`. B propose trois lead times à paiement 60 et
   aucune ref. Réponse : **15,60/14 avec claim verified chez A**, contre
   **16,20/30 sans claim chez B**. Le back office A[2] attribue explicitement
   une demi-concession au devis rival ; A[8], à r2, confirme le reste du pas.
3. **C1/r1, trace[4:6].** A propose le paiement rapide et lead21/28 ; C1
   répond 18,20/60/28. B propose lead21/28/35 à 60 et obtient 17,50/60/35.
   A force donc ici une livraison plus rapide sans besoin économique après
   35 jours ; cela lui coûte davantage dans la réponse initiale de C1.
4. **J1/r2 et C1/r2.** A obtient J1 14,70/14 (trace[7]) puis cite son offre
   r1 à C1, qui passe à 17,50/60/28 avec claim verified (trace[8:10]).
   B subit un **timeout J1/r2** (trace[6]), reçoit le maintien à 16,20
   (trace[7]), et C1 passe à 17,00/60/35 sans citation (trace[8:10]).
5. **Concessions suivantes.** Chez A : J1 r3 14,40, r4 14,30, r5 final
   14,20, toujours à 14 jours ; C1 r3 17,20 puis r4 final16,50, toujours
   60/28, avec citations J1-r3 puis J1-r5 toutes deux verified. Le back
   office A[17]/A[29] relie de nouveau demi-pas et complément à un rival.
   Chez B : C1 r3 16,80 puis r4 final16,70, à 60/35 ; J1 r3 15,70 puis
   r4 final15,40, à 30/28 ; aucune citation sur l'ensemble du parcours.
6. **Maintien/clôture.** A envoie deux questions sans feuille à J1 r6 et
   r7 : l'offre reste 14,20, mais son ID avance à J1-7. A accepte J1-7
   (trace[24]). B accepte **C1-4 à 16,70** (trace[18]), après que la trace
   serveur a enregistré J1-4 à **15,40** (trace[17]).

### Pourquoi B retire les leviers

`CASH_RE` de B ne comprend pas Zahlungsziel, présent dans l'ouverture.
Il ne charge aucun signal cash pour les DEMO absents du package. Le trio
comprend donc trois lead times, sans 14 jours. Restaurer uniquement le regex
A dans B remet exactement **13,54/14** dans le premier package J1 ; cette
ablation ne rétablit pas la citation rivale.

B exige qu'un rival soit idle, admissible aux must-haves **et** meilleur en C.
La feuille C1-0 échoue déjà à l'admissibilité, même avec busy vide : le test
le reproduit. Un fil en vol est un second filtre susceptible de supprimer
les offres suivantes ; l'état busy exact des workers n'est pas exporté.
A cite C1-0 et obtient un résultat **verified** ainsi qu'une raison interne
explicite. Confondre « levier commercial vérifiable » et « lot attribuable
maintenant » a supprimé un avantage observé. Les effets du paiement et du
claim sur chaque prix fournisseur ne peuvent pas être séparés numériquement.

### Timeout et publication : ce qui est prouvé

Le timeout J1/r2 est présent dans trace, session.moves et threads[J1].timeouts.
Les annexes J1/r1 de B comprennent un XLSX **et un nouveau PDF**, contre le
XLSX chez A. B hydrate les documents avant de publier localement la réponse.
Une hydratation lente peut donc expliquer le round perdu et un busy prolongé,
mais les exports ne permettent pas de mesurer cette durée ou de désigner
PDF, XLSX, HTTP ou CPU comme cause du timeout. Aucun « timeout mesuré à X s »
n'est affirmé ici.

Le bug d'attribution, lui, est reproductible : avec les vraies feuilles finales
et busy={J1}, B `_accept_best` exclut J1 et accepte C1 ; **latest et la greffe
renvoient {wait: True}**. Busy vide, B choisit correctement J1. L'ordre serveur
J1-final puis accept-C1 ne prouve pas que J1 était déjà publié/hydraté dans
le dictionnaire local. Une réponse encore en hydratation ou une fenêtre de
publication/réservation est compatible avec le résultat. Sans journal local,
la reconstruction exacte de cette fenêtre reste indécidable ; l'exclusion
busy est un mécanisme suffisant démontré, pas un timestamp inventé.

### Décomposition économique

La qualité est complétée par le standard de chaque fournisseur, même quand
sa feuille RFQ n'affiche pas les ppm.

| Attribution/feuille réellement exportée | Achat | Paiement | Qualité | C |
|---|---:|---:|---:|---:|
| A : J1 14,20/14/28/DAP | 170 400 € | 1 741,87 € | 528 € | **172 669,87 €** |
| B : J1 15,40/30/28/DAP, non accepté | 184 800 € | 1 232 € | 528 € | **186 560 €** |
| B : C1 16,70/60/35/DAP, accepté | 200 400 € | 0 € | 1 248 € | **201 648 €** |

La perte totale B−A de **28 978,13 €** vaut :

- **13 890,13 €** de termes J1 moins favorables : +14 400 € d'achat,
  −509,87 € de coût de paiement, qualité identique ;
- **15 088 €** supplémentaires en attribuant C1 plutôt que la feuille J1
  finale déjà exportée. Même la feuille J1 précédente à 15,70 coûte
  190 184 €, moins que C1.

C_open=214 296 ; C_best=156 738,78 ; alternative=238 800.
La feuille J1 exportée par B donnerait algébriquement **0,481886**, et non
0,219747. Ce chiffre ne prédit pas une session modifiée : il évalue des
termes déjà présents. Corriger seulement la clôture ne suffit donc pas à
retrouver le 0,723213 de A ; les leviers de négociation comptent aussi.

## Ce qu'il faut reprendre, et les limites de la preuve

La livraison [latest-proposed/](latest-proposed/) greffe relationship,
intel_bridge et les citations sur **latest**, en conservant son player.
[Notes de portage](LATEST_PORT_NOTES.md) et [patch](latest-proposed/pegasus.patch).

- Coûts de décision et de clôture : modèle fournisseur explicite, standard
  cash distinct des termes offerts, refresh avant calcul, domaine cash positif.
- Inversion de C(P) non monotone uniquement quand le modèle est disponible :
  minimum, deux branches, validation au centime, plafond ask dans le solveur.
  Budget infaisable : diagnostic et question, sans prix artificiellement bas
  ni relaxation silencieuse. Le calibrage pratique reste explicitement ex post.
- Briefs et signaux pour les **447 fiches/446 fournisseurs canoniques**, tous
  sets. Cash/gel activent les flags historiques ; capacité/couverture ajoutent
  des questions. Ils gardent sources et confidence, sans devenir des faits API.
- citable_claims sélectionnés à trois, ≤20 refs, usages suivis. Pièce, unité,
  pays, fournisseur, indices frais et faits privés sont revérifiés. Les ID
  de pièces numériques sont remplacés par « this part » dans les phrases,
  car le guard historique interpréterait leur numéro comme une mesure.
- Cibles uniquement practice ; aucune cible ni coût caché DEMO appris du score.

La preuve locale compare **28 décisions complètes et 78 packages** A→greffe
sur les quatre historiques, puis **10 scénarios de clôture** dont chaque
combinaison busy RFQ : zéro différence. Les packages A/A et B/B enregistrés
sont tous reproduits. Les six modules opérationnels inchangés sont vérifiés
au byte, `_done` à l'AST, CASH_RE et MIN_STEP gardés. Les recherches au centime
hors modèle sont identiques sur toutes les structures légales D01/D02 et
plusieurs budgets. Les DEMO ne déclenchent aucun chargement complet des dossiers.

Cela établit la conservation du comportement sur ces états, pas un nouveau
score hébergé ni une égalité des timings de transport. Sans nouveau renseignement
et avec la même exécution, les décisions sont inchangées ; les courses présentes
dans le player de A et la latence réelle restent des limites. Une future
injection de faits privés applicables active intentionnellement le modèle et
sort de cette preuve d'égalité. Les cas finaux connus changent volontairement :
leur score exige une mesure hébergée, interdite dans ce tour.

Ne pas reprendre la proposition complète du tour 4, son exclusion busy, son
regex cash resserré, le reclassement à chaque réponse, ni le remplacement de
l'inversion affine hors modèle. Ne pas transformer les corrections utiles
relationship/intel en modifications simultanées de la stratégie RFQ.

## Critique de A

**Constats de ces traces :**

1. D01 : A omet relationship dans ses coûts. Les **833,90 €** réellement
   exportés représentent 2,08 points de score sur 100. Sans modèle public
   applicable, cette omission est une borne optimiste, pas une estimation
   complète. La greffe l'affiche, sans inventer le coût de DEMO-F1.
2. D02 : C1 reçoit des packages lead21/28 alors que le buyer n'a pas de
   coût de retard avant 35. Sa réponse r1 monte à 18,20, contre 17,50/35
   chez B. L'effort inutile est observé ; son prix causal exact et le gain
   d'une correction ne sont pas identifiés. Conserver une variante35 mérite
   une ablation distincte après cette greffe.
3. Les questions J1 r6/r7 produisent deux mêmes prix, de nouveaux IDs et
   plusieurs annexes, sans gain chiffré. Garder un rival vivant aide C1 ; la
   seconde question paraît superflue dans l'ordre serveur, mais peut précéder
   la publication locale du final C1. Ne pas la qualifier de course prouvée.
4. MIN_STEP est 15 % d'un écart de C qui se réduit, pas un minimum de cents.
   La variante rapide J1 de A avance **13,54 → 13,99 → 14,10 → 14,14 → 14,16**,
   soit +0,45, +0,11, +0,04, +0,02 €. La plainte « one cent » évoquée dans
   ROUND5 provient d'autres parties ; elle n'apparaît pas dans ces quatre exports.
5. C1-0 incomplet est un levier verified ici ; la phrase ne démontre pas
   une attribution possible. Sur d'autres cas, comparer seulement les prix
   nominaux pourrait mal décrire la valeur de l'alternative commerciale.

**Risques statiques du code, sans incident A démontré par ces exports :**

- `wait` n'a pas de borne par horloge du fil. Même la meilleure offre qui
  ne bat pas l'alternative déclenche wait si elle est busy. Les clocks de
  60 s restent exposées ; aucun timeout A n'est observé dans ces deux cas.
- Proche du cap, `play.py` utilise `arena_kit.play.closing_move`, qui ne reprend
  ni les alternatives de feuilles, ni le modèle relationship, ni la protection
  busy de l'agent. La greffe conserve ce chemin : son modèle y est donc ignoré.
- Le player libère le verrou entre décision et réservation ; il enlève le
  fil d'inflight avant hydratation, puis effectue extraction/close sous verrou.
  Il garde le drainage du pool au retour. Ce sont des fenêtres et blocages à
  instrumenter ; ne pas attribuer le timeout de B à ce code A différent.
- `_done` ne passe pas par le guard. Les claims consommés à construction ne
  sont pas restaurés après rejet réseau ou suppression par guard. Le guard
  ignore les nombres près des offres, accepte une mesure quand aucun champ
  numérique n'est disponible, et ne garantit pas prix≤ask (tolérance1,25).
  Dans A, `_known` voit case.facts mais `_figure_ok` reçoit seulement pkg.facts.
  Pour les nouveaux claims connus, la greffe passe les faits fusionnés ; elle
  ne revendique pas un durcissement global du guard.
- A conserve une référence offerte dans `std`, et ses drivers seulement à
  l'initialisation. La greffe sépare la référence cash et actualise les drivers
  pour les fournisseurs connus ; elle garde les références historiques DEMO.

Ces risques méritent des changements séparés avec tests de clocks et une
mesure locale des états reçu/publié/hydraté. La recommandation principale
reste de préserver wait et les leviers commerciaux observés, puis porter
uniquement les calculs et renseignements applicables.

## Annexe — Tous les coups D02

Le numéro i désigne `session.result.trace[i]`. Toutes les feuilles acheteur sont indiquées ; aucune variante n’est omise.

### A-D02

| i | Round | Acteur / opération | Feuilles ou réponse | Citation / vérification |
|---:|---:|---|---|---|
| 0 | 0 | J1 : open | 17,1/30/28/? | — |
| 1 | 0 | C1 : open | 16,0/45/?/EXW | — |
| 2 | 1 | buyer → J1 : message | 13,68/60/28/DAP ; 13,54/14/28/DAP ; 13,68/60/21/DAP | offer:DEMO-C1-0 |
| 3 | 1 | J1 : open | 15,6/14/28/DAP | verified |
| 4 | 1 | buyer → C1 : message | 12,8/60/21/DAP ; 12,67/14/21/DAP ; 12,8/60/28/DAP | — |
| 5 | 1 | C1 : open | 18,2/60/28/DAP | — |
| 6 | 2 | buyer → J1 : message | 14,13/60/28/DAP ; 13,99/14/28/DAP ; 14,13/60/21/DAP | — |
| 7 | 2 | J1 : open | 14,7/14/28/DAP | — |
| 8 | 2 | buyer → C1 : message | 13,82/60/21/DAP ; 13,68/14/21/DAP ; 13,82/60/28/DAP | offer:DEMO-J1-1 |
| 9 | 2 | C1 : open | 17,5/60/28/DAP | verified |
| 10 | 3 | buyer → J1 : message | 14,24/60/28/DAP ; 14,1/14/28/DAP ; 14,24/60/21/DAP | — |
| 11 | 3 | J1 : open | 14,4/14/28/DAP | — |
| 12 | 4 | buyer → J1 : message | 14,28/60/28/DAP ; 14,14/14/28/DAP ; 14,28/60/21/DAP | — |
| 13 | 4 | J1 : open | 14,3/14/28/DAP | — |
| 14 | 3 | buyer → C1 : message | 14,53/60/21/DAP ; 14,39/14/21/DAP ; 14,53/60/28/DAP | offer:DEMO-J1-3 |
| 15 | 3 | C1 : open | 17,2/60/28/DAP | verified |
| 16 | 5 | buyer → J1 : message | 14,3/60/28/DAP ; 14,16/14/28/DAP ; 14,3/60/21/DAP | — |
| 17 | 5 | J1 : final_offer | 14,2/14/28/DAP | — |
| 18 | 6 | buyer → J1 : message | question de maintien du fil | — |
| 19 | 6 | J1 : final_offer | 14,2/14/28/DAP | — |
| 20 | 4 | buyer → C1 : message | 15,02/60/21/DAP ; 14,86/14/21/DAP ; 15,02/60/28/DAP | offer:DEMO-J1-5 |
| 21 | 4 | C1 : final_offer | 16,5/60/28/DAP | verified |
| 22 | 7 | buyer → J1 : message | question de maintien du fil | — |
| 23 | 7 | J1 : final_offer | 14,2/14/28/DAP | — |
| 24 | 7 | buyer → J1 : accept | offer:DEMO-J1-7 | — |

### B-D02

| i | Round | Acteur / opération | Feuilles ou réponse | Citation / vérification |
|---:|---:|---|---|---|
| 0 | 0 | J1 : open | 17,1/30/28/? | — |
| 1 | 0 | C1 : open | 16,0/45/?/EXW | — |
| 2 | 1 | buyer → J1 : message | 13,68/60/28/DAP ; 13,68/60/21/DAP ; 13,68/60/35/DAP | — |
| 3 | 1 | J1 : open | 16,2/30/28/DAP | — |
| 4 | 1 | buyer → C1 : message | 12,8/60/21/DAP ; 12,8/60/28/DAP ; 12,8/60/35/DAP | — |
| 5 | 1 | C1 : open | 17,5/60/35/DAP | — |
| 6 | 2 | buyer → J1 : timeout | horloge expirée, pas de feuille | — |
| 7 | 2 | J1 : open | 16,2/30/28/DAP | — |
| 8 | 2 | buyer → C1 : message | 13,83/60/35/DAP ; 13,83/60/21/DAP ; 13,83/60/28/DAP | — |
| 9 | 2 | C1 : open | 17,0/60/35/DAP | — |
| 10 | 3 | buyer → C1 : message | 14,39/60/35/DAP ; 14,39/60/21/DAP ; 14,39/60/28/DAP | — |
| 11 | 3 | C1 : open | 16,8/60/35/DAP | — |
| 12 | 3 | buyer → J1 : message | 14,25/60/28/DAP ; 14,25/60/21/DAP ; 14,25/60/35/DAP | — |
| 13 | 3 | J1 : open | 15,7/30/28/DAP | — |
| 14 | 4 | buyer → C1 : message | 14,88/60/35/DAP ; 14,88/60/21/DAP ; 14,88/60/28/DAP | — |
| 15 | 4 | C1 : final_offer | 16,7/60/35/DAP | — |
| 16 | 4 | buyer → J1 : message | 14,48/60/28/DAP ; 14,48/60/21/DAP ; 14,48/60/35/DAP | — |
| 17 | 4 | J1 : final_offer | 15,4/30/28/DAP | — |
| 18 | 4 | buyer → C1 : accept | offer:DEMO-C1-4 | — |

