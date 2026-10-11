# Questions pour Claude

## Q1 — Chiffres citables et chiffres internes

`facts.json` ne contient ni `sup:…`, ni `part:…`, ni les finances de
`supplier_intel`, ni les événements `EV-…`, ni les factures ou le spend cube.
La consigne « chaque chiffre avec un ID facts.json » est donc incompatible avec
un profil financier complet et avec un prix calculé qui n'existe pas dans ce fichier.
**Option recommandée et retenue :** exporter trois couches explicites :
`verified_facts` (copies exactes avec ID), `context` (observations internes avec
table, clé, colonne, jamais présentées comme citables), `derived` (formule et
entrées sourcées). Aucun ID inventé. Claude doit citer uniquement les faits
vérifiés et les variations d'indices permises par l'API.

## Q2 — Cas d'entraînement et disponibilité hors ligne

L'API précise que les fichiers des cas sont servis par l'API et ne font pas
partie du package. Aucun fichier P01–P19 dans `arena_kit` ; des documents
déclencheurs portent ces suffixes. **Option retenue :** reconstruire une
cartographie partielle depuis ces documents et les RFQ liées aux pièces ;
ne pas inventer `hosted`, objectifs, options, alternatives ou must-haves.
À compléter par Claude avec les fichiers de cas dont il dispose déjà.

## Q3 — Date de base du prix ajusté par les indices

Le prix ERP courant n'est pas toujours le prix standard du matériau. Les
indices ont des retards de publication et les clauses contractuelles peuvent
avoir leur propre base. **Option retenue :** prix conditionnel en vigueur à la
date du package, confirmé par un PO non obsolète, indices depuis le mois de
prise d'effet de cette condition jusqu'au dernier mois disponible de chaque
série. Fournir aussi une fenêtre annuelle distincte, citable, sans attribuer
sa variation au même horizon que le prix ajusté. Les poids non indexés restent fixes.

## Q4 — Release du dimanche

La release annoncée est additive (faits nouveaux, CSV et documents), sans
remplacement des faits v1. **Option retenue :** découverte automatique du
dossier `release-sunday` voisin ou enfant, support d'un chemin explicite,
fusion des nouveaux IDs et erreur en cas de collision incompatible. Aucune
connexion réseau ; la release doit déjà être présente sur disque.

## Q5 — Marge et trésorerie

Le package ne donne pas de bilan de trésorerie ni de marge réelle actuelle.
**Option retenue :** signaux textuels pour le cash ; estimation de marge par
pièce uniquement avec un should-cost applicable, intervalle d'erreur et
avertissement sur paiement/fret/outillage. Aucune marge de société inventée.

## Q6 — Publication des salaires après la dernière condition

Sur le câble, la condition courante commence en juillet alors que LCI-C
s'arrête en juin. **Option retenue :** conserver juin comme dernière
observation pour les deux bornes de cette composante, donc mouvement observé
nul ; signaler `ok_with_publication_lag` et ne pas assimiler cela à une
prévision de stabilité des salaires. Une lacune interne à la série continue
à désactiver le calcul plutôt que de fabriquer une interpolation.

## Tour 2

### Q7 — Peut-on retrouver le package caché depuis C_best ?

Un coût total scalaire ne détermine pas un prix et plusieurs conditions uniques.
La pénalité de relation peut même rendre C non monotone en prix et créer deux
racines. **Option retenue :** énumérer les options admissibles, inverser C pour
chaque package, conserver les racines et vérifier les prix au centime. Présenter
ces packages comme candidats mathématiques, jamais comme le plancher accepté
du fournisseur. Distinguer cible à score 0,99, minimum du modèle et acceptabilité.

### Q8 — Coût fournisseur et standards manquants dans les exports

Les PDF de devis ne sont pas fournis avec les sessions ; les chiffres internes
restent masqués. **Option retenue :** standards contextuels du référentiel,
conditions de clôture observées, coût complet should-cost applicable et cash
estimé à 8 % par défaut, avec scénarios 4/8/16 %. Pour P02, calibrer aussi une
estimation conditionnelle du coût sur la pénalité de relation observée, sans
prétendre identifier le taux caché. Publier les écarts de reproduction.

**Affinement après les calculs :** les paires prix/paiement fournissent des
taux d'équivalence conditionnels (P02 ≈6,585 %, P03 ≈4,069 %), utilisés quand
les autres termes sont identiques. Leur égalité de valeur cash reste une
hypothèse, car une concession commerciale peut expliquer le changement.
Pour P01, la borne haute compatible avec une pénalité nulle rend C_best
inatteignable sous le taux supposé ; le playbook retient donc aussi le
scénario bas du should-cost, explicitement sélectionné ex post. Aucun
paramètre caché identifié ni prédiction indépendante revendiquée.

En RFQ, C_best est le meilleur coût de tous les bidders : une cible
algébrique à ce niveau chez chacun ne prouve pas qu'il est acceptable chez
chacun. Le fournisseur du meilleur package reste non identifiable.

### Q9 — P04 : allonger la durée suffit-il ?

Douze mois laissent bien 94 000 € de besoin au prix de secours, mais acheter
deux ans au prix proposé peut coûter davantage : le prix de secours est inférieur
au prix négocié. **Option retenue :** calculer chaque durée au même prix et
contester une attribution automatique du score nul à la seule durée.

### Q10 — Garantie des citations et portée des observations

Sans appeler l'API, on peut garantir les IDs, valeurs, fenêtres et critères
documentés, pas la lecture linguistique du moteur ni l'effet commercial.
**Option retenue :** phrases anglaises simples, un chiffre par argument,
filtrage des IDs déjà utilisés, maximum trois lors de la sélection et devis
rivaux uniquement autorisés par le cas. Les quinze exports contiennent deux
replays P01 identiques : ne pas les compter comme réplications indépendantes.


## Tour 3

### Q11 — Relecture des traces sans inventer les réponses contrefactuelles

Les traces contiennent les réponses aux anciens messages, pas aux propositions
du nouvel agent. **Option retenue :** rejouer l'agent sur chaque état enregistré,
valider ses actions et ses coûts, sans attribuer un score de négociation réel
au replay. Ajouter un fournisseur synthétique déterministe pour tester des
invariants et des politiques ; son score restera celui du simulateur.

### Q12 — Corrections de l'agent et périmètre autorisé

La copie `pegasus-review/pegasus/` est en lecture seule. **Option retenue :**
charger son code en mémoire, conserver les défauts reproduits et livrer les
correctifs séparément dans `pegasus-review/proposed/`, accompagnés d'un patch
concret. Ne pas modifier l'original, appeler l'API ou dépenser le quota partagé.

### Q13 — Coût relationnel et transfert à la finale

`economics.cost` appelle `total_cost` sans fournisseur, donc relationship vaut
zéro, y compris pour P02 où le résultat en contient 112 075,30 €.
**Option retenue :** intégrer estimation explicite et scénarios pour les seuls
objectifs concernés ; adapter simultanément l'inversion en prix, car C peut
être non monotone. Réserver les cibles C_best et les calibrations du playbook
au set practice. En finale, construire l'estimation depuis les données et
les documents disponibles, avec signal explicite si le coût reste inconnu.

### Q14 — Synchronisation des fils RFQ

Le verrou de décision ne couvre pas les requêtes en cours. Une décision
peut accepter sur un autre fil pendant que son offre change ; un échec de
close arrête actuellement tous les workers même si le cas reste ouvert.
**Option retenue :** réserver la clôture, attendre les envois déjà engagés,
réactualiser le choix puis clôturer ; confirmer l'état ended avant l'arrêt.
Sortir tous les téléchargements et appels réseau du verrou de décision.

### Q15 — Relancer après agreed et final_offer

Le simulateur ne justifie pas de supprimer la relance unique après un accord
rapide : une variante sans relance obtenait 0,571 au lieu de 0,857 dans un
scénario synthétique. **Option retenue :** conserver une relance agreed,
avec budget réalisable et interrupteur `reopen_agreed=False`, sans la présenter
comme optimale. Laisser `push_after_final=False` : le prochain test doit
isoler une contrepartie nouvelle et le risque de perdre l'offre finale.

### Q16 — Marge de cap, erreurs de clôture et quota partagé

L'API demande un timeout HTTP d'au moins 180 s. L'ID périmé est documenté en
422, alors que 409 peut signaler une session terminée ou un retard. Le helper
SDK de reprise ne reconstitue les termes que depuis les timeouts.
**Option retenue :** rafraîchir les vrais messages et l'état sur 422/409 de
clôture ; marge de drainage proposée 210 s, configurable, à valider avec la
latence réelle plutôt que réduire arbitrairement le timeout officiel.
Cette marge ne couvre pas forcément plusieurs fichiers/retries successifs.
Les dix sessions restent non démarrées ; huit priorités et deux réserves,
avec un journal central de réservation pour les quatre participants.

## Tour 4

### Q17 — Clôture sans drainage et périmètre RFQ

La réponse de Claude invalide le drainage bloquant proposé au tour 3 : un fil
inactif peut dépasser 60 s. **Option retenue :** conserver `busy`, réserver
l'offre choisie sous verrou, clôturer hors verrou immédiatement parmi les fils
sans requête en cours, puis resynchroniser sur 409/422. Aucun worker n'attend
la réponse d'un autre fournisseur. Le test d'attente RFQ sera adapté à cet
invariant ; aucune nouvelle stratégie RFQ ni simulateur concurrent de Fable.

### Q18 — Dossiers en finale et signaux interprétés

Les 40 fournisseurs finaux viennent du package existant. **Option retenue :**
charger `agent_brief` et les signaux sourcés pour chaque fournisseur du package,
quel que soit le set. Les cibles/calibrations ex post restent practice-only.
Cash, gel, capacité et couverture des matières orientent les packages ou les
questions ; leurs textes internes ne deviennent pas des claims numériques.
Une nouvelle combinaison fournisseur/pièce garde les signaux du fournisseur,
mais aucune estimation de prix d'une autre pièce.

### Q19 — Paramètres et coût relationnel

**Option retenue :** garder tous les réglages PEGASUS_* existants et bench.py,
conserver leurs valeurs par défaut, ajouter une marge de clôture paramétrable.
Le plafond ask sera une borne du solveur et du contrôle au centime : un min()
appliqué après l'inversion peut dépasser le budget si C(P) est non monotone.
L'estimation relationship reste une hypothèse explicite, jamais un coût caché
identifié. Claude doit mesurer marge et latences en sandbox avant la finale.

### Q20 — Validation du portage et prochaines mesures

Les 22 tests adaptés et 20 contrôles supplémentaires passent hors ligne.
Le replay reste un contrôle d'actions, pas un score ; relationship central
modifie sensiblement des décisions et rend deux budgets P03 infaisables.
**Option retenue :** livrer le modèle avec son statut, ses budgets et le
plafond ask visibles, puis comparer au coût observé. Faire d'abord une
référence D01/D02 aux paramètres 0,80/0,94, mesurer les transports et la marge,
puis seulement le plan practice coordonné P02/P03. Les DEMO ne possèdent pas
les dossiers des fournisseurs réels : les tests locaux couvrent cette
intégration finale, les claims hébergés restent à contrôler par Claude.

## Tour 5

### Q21 — Identifier la régression sans attribuer un score au replay

Les traces A/B contiennent les décisions, réponses, back office et timeouts,
mais aucun timestamp de réception/hydratation et aucun contenu PDF/XLSX.
**Option retenue :** expliquer chaque coup avec chemins JSON exacts, coûts
recalculés et reproductions de décisions. Distinguer la réponse observée du
mécanisme reconstitué ; ne pas inventer les latences du timeout B/J1 ni un
score sandbox de la future greffe.

### Q22 — Réviser le compromis clôture du tour 4

L'exclusion busy garantissait un ID non périmé mais pouvait attribuer le lot
au fournisseur plus cher. Le résultat B/D02 démontre cette régression.
**Option retenue :** garder les nouvelles politiques `_done`, `wait` et
MIN_STEP de Claude dans le patch minimal, ainsi que son player et guard.
Auditer séparément le risque de dépassement des 60 s et le chemin proche
cap ; ne pas réintroduire silencieusement une clôture immédiate sur C1.

### Q23 — Intégration utile sans changer la trajectoire DEMO

**Option retenue :** greffer modèle relationship + solveur non monotone et
intel_brief sur latest, en conservant strictement les branches historiques
lorsqu'aucun modèle/dossier applicable n'existe. Les fournisseurs DEMO ne
sont pas dans le package : leurs messages, chiffres, citations et décisions
pour les mêmes états doivent rester identiques. Les cibles/calibrations
ex post restent practice-only ; aucun coût caché DEMO n'est déduit du score.

### Q24 — Quel niveau de preuve de non-dégradation sans réseau ?

**Option retenue :** conservation exacte A→greffe de 28 messages, 78 packages
et 10 clôtures avec états busy, source player inchangée et coûts hors modèle
sans dérive d'arrondi. Les standards sont des fixtures déclarées, faute de
PDF. Cette preuve ne constitue pas un score nouveau ni une mesure de timings
HTTP. Les score A/B sont ceux des exports ; 0,481886 est uniquement le calcul
sur la feuille J1 finale exportée par B, pas un résultat du patch.

### Q25 — Modèle/citations actifs et limites assumées

**Option retenue :** modèle déclaré stabilise/secure_supply, standard cash
actualisé avant calcul, inversion à deux branches avec plafond ask. Budget
infaisable : diagnostic/question sans relaxation. Les faits privés passent
avant le public et alimentent aussi le guard des nouveaux claims connus.
Les signaux cash/gel enrichissent A ; capacité/couverture posent des questions.
Le cycle d'usage des claims, wait et closing_move proche cap restent ceux de
A ; aucune promesse de rollback, borne d'attente ou modèle au cap n'est faite.
Les mesures supplémentaires relèvent des points à débattre du REPORT Tour5.

## Tour 6

### Q26 — Référence jouée et correctifs attendus

Les fichiers initiaux latest-r6 contiennent encore les défauts P08/P11.
**Option retenue :** figer leurs onze modules en référence, analyser les
traces sans modifier la copie de Claude, puis vérifier les fichiers qu'il
met à disposition. Une question asynchrone précise leur disponibilité ou
emplacement ; son absence de réponse ne vaut ni correctif reçu ni validation.

### Q27 — Causalité et séquence plausible

**Option retenue :** distinguer coût algébrique, réponse observée et réponse
non jouée. Les 542 256 € de besoin non couvert P08 ne sont pas un gain gratuit :
acheter la deuxième année ajoute aussi son prix. P11 a une promesse fausse,
mais la perte de score due à cette phrase seule n'est pas identifiable.
Les contreparties chargeback/ppm et la confirmation du volume fixe seront
étayées par l'ancien échange Kalwisz, sans introduire un levier non négociable.

### Q28 — Correctifs reçus et verdict pour dix sessions

L'utilisateur confirme les correctifs dans latest-r6 et les scores sandbox
D01 0,969 / D02 0,702. Le rejeu vérifie effectivement les nouvelles fonctions,
sans toucher au code de Claude. **GO pour dix sessions practice mesurées** :
aucune nouvelle erreur technique sur 179 décisions, 22 tests réussis.
Les réponses historiques ne permettent pas de prédire les nouveaux scores.
Les redondances de contrats longs, le délai P10 et la clause P18 restent
des points à suivre ; le modèle relationship reste absent de ce snapshot.

## Tour 7

### Q29 — Comment attribuer l'écart à C_best sans connaître ses termes privés ?

**Option retenue :** partir du C_deal officiel, calculer les sensibilités de
termes au même prix, puis afficher le résidu équivalent au prix. Les feuilles
sans clause refusées restent des bornes théoriques, pas un gain accessible.
Relationship est affiché séparément et maintenu constant dans les seuls
équivalents de revue. C_best et records n'entrent jamais dans les règles runtime.

### Q30 — Qu'est-ce qu'une nouvelle contrepartie après une finale ?

**Option retenue :** une concession au-delà de l'enveloppe déjà proposée
dans les champs demandés et négociables ; pas simplement un nouveau prix,
un délai30 après avoir offert14, ou un assemblage de giveaways épuisés.
Une fois maximum, assez de tours pour répondre/clore, pas de RFQ/busy,
et priorité à une meilleure alternative déjà proposée par le fournisseur.
Le maintien de la finale en cas de refus est demandé, sans prétendre le garantir.

### Q31 — P01 novembre est-il une régression de latest-r7b ?

**Option retenue :** intégrer la distance normalisée de r7b, qui modifie
uniquement economics ; agent r7/r7b identique. Novembre est déjà choisi
dans r7 et minimise C sous le prix courant. Au-dessus, avril domine et le
recalcul est testé. Le danger vient d'une finale au-dessus du prix courant
avec ancienne date, plus de relationship ignoré : la sensibilité brute de date
ne permet pas de promettre un gain officiel. Conserver les décisions actuelles
P01 dans la proposition ; mesurer les nouveaux résultats séparément.

### Q32 — Que signifie « aucun autre cas ne régresse » sans réseau ?

**Option retenue :** preuve sur les décisions complètes des autres cas récents,
les budgets/must-haves, les identifiants de clôture et les décisions DEMO.
Une relance qui n'a aucune réponse dans la trace est déclarée censurée.
Le replay n'invente ni cette réponse, ni une garantie de score futur.
La suite couvre les pièges de timing via un état busy explicite et le protocole
de renvoi puis acceptation d'une alternative sous un nouveau principal.

## Tour 9

### Q33 — Peut-on apprendre une loi de concession et le déclencheur de finale ?

**Option retenue :** mesurer les pas avant agreed, à structure constante
des deux côtés, dédupliquer les traces et bootstrapper par session. Séparer
relation descriptive et causalité : P18 baisse de 0,10 avec des pas acheteur
variables ; P07 ne fournit que des répétitions du même couple. Aucune question
sans feuille, menace ou demande explicite au manager dans les observations
open comparables : leur effet reste inconnu. Ni β ni record privé par cas ne
deviennent une règle runtime.

### Q34 — Quelle portée donner au gain annoncé des nouvelles tactiques ?

**Option retenue :** donner une plage incluant zéro, en points du cas, motivée
par un pas supplémentaire observé ou une fraction de l'écart au record rapporté.
Le classement utilise une confiance ordinale, pas une probabilité calibrée.
Validation commerciale, BAFO et capacité sont implémentées séparément, sans
tour supplémentaire pour les deux premières. Le replay technique apparié ne
prévoit pas les réponses à leurs nouveaux messages. D02 permet de tester les
deux premières, mais ne représente ni la capacité P10 ni les clauses P02/P18.
Aucun essai réseau n'est exécuté au tour 9 ; les gains doivent être mesurés.

## Tour 10

### Q35 — Que mesure la précision du lecteur sur notre gold ?

**Option retenue :** annotations sémantiques explicites de toutes les phrases,
0..n types, avec provenance et regroupement des formulations numériques.
Comparer le détecteur initial et proposé par phrase et formulation ; ne pas
pondérer les copies email/trace/raison. Les chiffres 99,8 % / 95,5 % décrivent
le corpus utilisé pour développer les regex. Pas de second annotateur ni de
performance hors échantillon revendiquée ; les types rares restent peu étayés.
Une citation LLM valide garantit la provenance, pas la justesse de son type.

### Q36 — Quels cas justifient une nouvelle session practice ?

**Option retenue :** exiger une différence de texte ou de feuilles démontrée
sur la dernière archive, et fournir les décisions appariées. Les cinq cas
P05/P07/P18/P08/P02 satisfont ce critère. Contraintes et coûts restent vérifiés,
mais un message modifié rend la réponse suivante non observée. Les nouvelles
contraintes de série/durée/délai et l'abandon du signal cash automatique sur
Zahlungsziel peuvent aider ou nuire ; aucun nouveau score n'est déduit du replay.
Au tour 10, aucun appel réseau ni nouvelle session n'est exécuté.
