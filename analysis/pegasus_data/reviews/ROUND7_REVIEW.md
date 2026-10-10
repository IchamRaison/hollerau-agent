# Revue du tour 7

La livraison est [latest-r7-proposed](latest-r7-proposed/), avec le départage
de latest-r7b intégré. Seuls agent.py et economics.py changent. Les originaux,
le player, les claims, le guard et les données restent intacts. Aucun réseau.
Les résultats hébergés ci-dessous appartiennent aux exports ; le patch n'a
pas de nouveau score. Les valeurs C_best servent à cette revue uniquement.

## Où reste l'écart ?

Sélection des lots par `summary.created_at` : dernier = lot 2, avant-dernier
= lot 1, puis ancienne négociation du kit. Le [JSON de revue](../intel/generated/ROUND7_REPLAY.json)
conserve les coûts officiels, les raisons, les textes, les back offices et les
indices précis dans les traces. Il couvre les dix cas practice enregistrés.

| Cas | C_deal lot 2 | C_best | Écart | Termes / prix à prix inchangé |
|---|---:|---:|---:|---|
| P02 | 2 259 084,85 € | 2 235 514,05 € | 23 570,80 € | Termes déjà minimaux hors relationship ; baisse de prix nécessaire. Relationship final : 611,74 €. |
| P11 | 772 501,50 € | 722 500,02 € | 50 001,48 € | 715,50 € de qualité évitables à cb500 ; 49 285,98 € restants avec ces termes idéaux. |
| P05 | 245 267,34 € | 223 424,17 € | 21 843,17 € | Paiement 90 au même prix : 4 081,50 € ; reste prix 17 761,67 €. Le fournisseur n'a pas accepté ce report gratuitement. |
| P07 | 329 020,80 € | 299 241,49 € | 29 779,31 € | 24 mois/90 jours déjà minimaux ; tout le résidu est équivalent à un écart de prix. |
| P18 | 257 458,63 € | 222 651,27 € | 34 807,36 € | Sans clause : 7 913,43 €, mais cette structure est refusée. Clause autorisée à deadband5 : 5 652,45 € à prix/paiement constants. |
| P10 | Pas de deal | 1 328 926,89 € | Non défini | Lot 1 : écart réel 264 082,71 €. Lot 2 : timeout après finale, pas un écart de prix mesuré. |

Cette partition est une sensibilité de la fonction publiée, pas la structure
privée ayant produit C_best. Le coût relationship est maintenu constant dans
les équivalents de prix : il ne le resterait généralement pas dans une
négociation réelle. Aucun gain de prix/termes n'est ajouté deux fois.

### P02 : volume confirmé, données neutres, clause exploitable

Lot 2, retours r1–r4 : le fournisseur reconnaît le volume ferme, répond aux
données de forecast, puis réduit la variante paiement14 de 368,68 à 366,75 €.
Le package principal à 371,92 €/90 jours demeure moins cher en C : la
variante rapide vaut 2 264 940,34 € hors relationship. Citer un prix inférieur
ou reprendre le paiement rapide seul ne capture donc pas l'écart.
Volume 6 110 et durée 12 mois sont fixes : aucune augmentation autorisée.

L'ancien kit r1 obtient 348,39 €/30 jours avec CU-NOTATION/deadband5 ; r2
stagne, r3 paie une extension de paiement, r4 clôture à 349,36 €/45 jours.
Son score 0,228 est inférieur aux deux lots Pegasus 0,502. La clause est une
contrepartie que ce fournisseur accepte, sans être une amélioration gratuite.
Règle : introduire une clause légale à prix compensé, puis n'en offrir davantage
après finale que si sa protection dépasse celle déjà proposée. L'augmentation
de risque et la marge sustainable sont les limites ; 368,03 € à termes finaux
et relationship constant n'est qu'un équivalent algébrique du C_best.

### P11 : faible chargeback et qualité sont des monnaies distinctes

Lot 2 r1 : accepte 300ppm/cb300 à 48 €, propose 2 500ppm à 47,50 €, mais
cette alternative viole le must-have 1 500ppm. r2 baisse à 47,50 ; r3 tient ;
r4 baisse à 47 ; r5 finale inchangée. Les demandes de paiement accéléré
continuent alors que les 60 jours sont fixes. Les chiffres sont reconnus,
mais le fournisseur dit protéger sa marge. Les trois feuilles restent centrées
sur cb500, cb300 et le même petit ensemble de ppm.

L'ancien kit r1 montre 47 €/300ppm/cb0 contre 48,50 €/1500ppm/cb300.
Après confirmation explicite de 15 900/an/12 mois/56 jours, r3 accepte
46,70 €/300ppm/cb0, C=769 162,50 €, soit 3 339 € de moins que le lot 2.
Les tentatives suivantes de rajouter cb300 échouent. Cette observation donne
une direction de trade ; elle ne prouve pas qu'un prix 43,90 sera accepté.
Règle : explorer ensemble ppm et chargeback, en respectant le must-have et
le budget C, et répondre explicitement que le paiement est fixé. Le compromis
0 chargeback / 1 500ppm et celui 0 / 300ppm ont des prix différents à C égal.
Risque : hypothèse sur ppm réel et cash fournisseur ; notre préférence utilise
le standard du devis et le taux public, pas un modèle privé ou C_best.

### P05 : la concurrence a déjà donné le principal mouvement

Les back offices r1 annoncent la moitié de la baisse sur un devis rival
sensiblement inférieur, r2 « Checked: give the rest of the step ». Dralveck
accepte 28,77 €/14 jours/28 jours en r2 ; les tentatives après accord n'obtiennent
plus de baisse. Hrvelec réduit ensuite 34 → 33,50 → 33 → 32,50 € en réponse
au cash et, une fois, au nouveau devis rival ; il reste plus cher. L'autre
concurrent finit à 30,28 €. Les textes libres et prix des sheets divergent
parfois ; seule la feuille structurée est utilisée pour décider.

Les timeouts du kit expliquent son zéro, les deux lots Pegasus valent 0,734.
Règle possible : rafraîchir seulement un vrai nouveau devis rival, préserver
son fil jusqu'à clarification interne, obtenir le paiement rapide en échange
d'une baisse suffisante pour couvrir son coût acheteur. Volume/durée sont fixes.
Risques : attendre longtemps ou réouvrir l'accord peut perdre la meilleure
offre. Le patch préserve _done, wait et le player ; il ne promet pas d'éliminer
des timings non présents dans les exports.

### P07 : une proposition combinée, pas des arguments déjà reconnus

r1 échange cash et 24 mois contre 5,59 €/90 jours, alternative 5,51 €/14.
r2 concède 5,52 €/90, alternative 5,44 €/14 ; cette dernière coûte 744,53 €
de plus. Le kit a obtenu un accord 36 mois, sans baisse à ses tentatives
suivantes. Les données de livraison/prix sont reconnues mais neutres, le
forecast est déjà pris en compte. Les feuilles Pegasus ont proposé 36 mois
et paiement14 séparément ; leur combinaison ferme peut rester une hypothèse
à tester avant la finale, avec le périmètre des quatre pièces et l'unité bundle.

Règle : exprimer la consolidation complète et proposer un package qui combine
cash et sécurité de durée, avec prix recalculé. Le volume supérieur n'est pas
négociable. Risque : 36 mois n'apportent aucun gain C sur cet horizon, et leur
valeur commerciale est incertaine. Le patch précise le périmètre du bundle,
mais n'assimile pas un réarrangement d'anciens giveaways à une nouvelle
contrepartie après finale. Il ne prétend pas capturer les 29 779 € entiers.

### P18 : accepter la famille de clause, négocier sa protection et le prix

r1–r4 répètent que 24 mois exigent AS-14404 ; chaque fois Pegasus renvoie
trois offres sans index. Le fournisseur accepte néanmoins 24 mois et baisse
5,60 → 5,50 → 5,40 → 5,30. Il a déjà proposé la clause deadband5 dans ses
alternatives rapides, mais le prix/paiement rendent la dernière plus chère :
C=260 880,12 €, +3 421,49 € contre le principal. L'ancien kit obtient une
clause5/36 mois/60 jours dans une alternative et clause3 dans le principal,
sans obtenir une bonne clôture (score 0,265).

Règle : reconnaître l'exigence structurée et mentionnée, offrir la même famille
avec deadband autorisé, recalculer le prix et conserver une variante cash qui
porte réellement la clause. Risque : accorder une clause non demandée ou trop
protectrice consomme C ; son acceptation ne garantit pas le prix compensateur.
Le gain de 5 652 € à prix constant est une sensibilité, pas une offre obtenue.

### P10 : protocole d'abord, puis coût de capacité

Lot 2 r1 : principal 33,80 €/42 jours/23 400/24 mois ; alternative 31,90 €/
54 jours. Le timeout r2 retire l'offre : le zéro n'est pas une erreur du
classement économique. latest-r7/b renvoient désormais l'alternative comme
notre sheet, puis peuvent accepter l'identifiant principal confirmé.
54 jours ne sont pas dans nos options : le renvoi utilise 56 jours, ajoutant
4 800 € de retard. Il reste 55 912,80 € moins cher que le principal, hors
relationship : ce bénéfice appartient au correctif de Claude, pas à notre patch.

Lot 1 : la demande 35 jours est citée comme coût d'overtime ; le kit obtient
33,50 € et l'accord sur 36 mois à son second retour, contre 33,70 € lot 1.
Le délai 42 jours évite le premium superflu 35, sans valeur C perdue.
Règle : préférer les termes proches à prix égal, puis proposer un délai plus
souple/durée supérieure seulement avec compensation de prix, must-have intact
et assez de tours pour confirmer. Risque : 56 jours coûtent 33 600 € de retard,
et la sécurité fournisseur impose de considérer relationship. Le volume fixé
par nos options ne permet pas d'inventer une hausse de demande.

## Classement des règles et patch retenu

Les notes gain/confiance sont ordinales (1–5), des jugements de revue ; leur
produit n'est ni une probabilité ni une prévision monétaire de score.

| Rang | Règle générale | Gain × confiance | Preuve / risque sur d'autres cas |
|---|---|---:|---|
| 1 | Menus de vrais trades : préférences observées, qualité/chargeback ensemble, clause exigée et compensation au C | 4 × 4 = 16 | P11/P18 et ancienne clause P02 ; risque P08 si l'exigence est extrapolée ou le prix compensé refusé. |
| 2 | Une relance finale avec giveaway au-delà de l'enveloppe déjà proposée, budget inférieur à la finale, puis clôture | 3 × 3 = 9 | Clause plus protectrice P02, délai plus souple P10 ; P07/P11 ne doivent pas recevoir une relance recyclée. Risque de retrait d'une finale. |
| 3 | Volume/durée additionnels et bundle complet, uniquement champs légaux | 3 × 2 = 6 | Ancien P10/36 mois ; P02/P05/P07/P11 ont du volume fixe. Risque d'achat inutile P03. |
| 4 | Breakdown : demander le pont coûts directs → coût complet/cash, sans automatiser un plancher | 2 × 2 = 4 | Attachement annoncé n'est pas un coût complet ; le plancher sandbox a chuté à 0,534. Risque D02 déjà observé. |
| 5 | Modèle explicite de marge sustainable après calibration d'unité/taux | 3 × 1 = 3 | P01 relationship 11 778 €, P02 612 € ; erreurs de modèle peuvent coûter davantage que le gain visé. |

La première règle garde le meilleur prix réalisable au C, le départage distance
de r7b et le seuil existant 90 %. Les variantes peuvent varier plusieurs champs
pour révéler une vraie contrepartie. La clause obligatoire exige aussi une
famille présente dans une offre structurée légale ; une mention dans les coûts
seule ne l'impose pas. L'exigence est mémorisée, les négations sont prises en
compte. Les paramètres fixes et les unités sont décrits fidèlement.

La seconde règle garde MIN_STEP de l'écart acheteur, propose uniquement des
champs négociables, demande le maintien de la finale si refus, réserve réponse
et clôture, et ne se déclenche qu'une fois. Elle exclut RFQ, busy, playbook,
meilleure alternative déjà pricée, anciens giveaways et intermediate payment
moins favorable qu'un délai déjà proposé. Le maintien demandé à un fournisseur
n'est pas une garantie contractuelle : une session future peut retirer son offre.

## P01 et l'information latest-r7b

Localement, agent.py r7/r7b est identique ; r7b ajoute distance à economics.
Les deux ouvrent déjà en novembre. À 118,94 < prix courant 126,53, novembre
minimise C. Les probes 126,52 / 126,54 confirment le basculement novembre /
avril et le recalcul de best_for_target : aucune date n'est gelée.
La distance est normalisée pour les nombres ; les dates restent une distance
binaire, ce qui ne code pas une préférence pour avril.

Risque limité mais réel à la clôture : la contre-offre acheteur r4 126,10
reste sous le prix courant, mais la finale fournisseur 129,80 le dépasse.
À ce même prix, reporter à avril économiserait 11 137,98 € hors relationship.
La marge/supplier value changent aussi : le résidu officiel à C_best est
seulement 715,47 €, avec 11 778,11 € de relationship. On ne peut pas promettre
le gain brut ni prendre 0,995 → 0,987 comme effet causal du départage r7b.
Le patch garde toutes les décisions actuelles P01 identiques à r7b.
Sandbox 0,979/0,702 est l'information fournie par l'utilisateur ; ces scores
n'appartiennent pas au patch et ne sont pas réestimés depuis ses messages.

## Reproduction et limites

`python3 -m intel.review_round7` puis `python3 -m unittest intel.test_round7 -v`.
Les patches FROM_R7.patch et FROM_R7B.patch s'appliquent dans la copie de
module correspondante. Aucun nouveau modèle, client ou player n'est requis.
Le JSON identifie les relances finales dont aucune réponse n'est enregistrée.
La non-régression prouvable porte sur validité, budgets, protocoles et décisions
comparables. Les réponses restant historiques, aucun replay ne garantit un
classement futur ou la non-dégradation des scores après messages modifiés.

Validation finale : **27 tests passent**, **39 traces/240 décisions fournisseur**
et **50 décisions aux instants acheteur** ne produisent aucune nouvelle erreur
technique. P01/P03/P04 récents et toutes les décisions D01/D02 sont identiques
à r7b ; les clôtures comparables restent identiques. La finale P02 reçoit une
relance clause3/paiement14/358,33 € dont la réponse est absente : son gain
reste non mesuré. Les deux patches passent check/application et reproduisent
exactement les onze modules, avec neuf modules conservés ;
[empreintes et validation](../intel/generated/ROUND7_VALIDATION.json).
