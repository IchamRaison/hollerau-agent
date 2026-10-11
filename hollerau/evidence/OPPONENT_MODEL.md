# Modèle du fournisseur : note de lecture (Williams et al.)

Nevil (avec Claude), dimanche 11/10/2026, 07:35. **Note seulement** : aucun code, rien dans `hollerau/pegasus/`, aucune session.

Sources :
- Williams, Robu, Gerding, Jennings, « Negotiating concurrently with unknown opponents in complex, real-time domains », ECAI 2012 ([TU/e](https://research.tue.nl/en/publications/negotiating-concurrently-with-unknown-opponents-in-complex-real-t/)). Le PDF renvoie 403 : seul le résumé a été lu.
- Méthode de base lue en entier dans deux articles de la même équipe : [IJCAI 2011](https://eprints.soton.ac.uk/271965/1/ijcai11.pdf) et [IAMhaggler2011](https://eprints.soton.ac.uk/273104/1/acan2011.pdf) (3e à ANAC 2011).

## La méthode en 5 lignes

1. On note chaque offre de l'adversaire avec l'utilité qu'elle **nous** donne, et on garde le maximum de chaque fenêtre de temps pour réduire le bruit.
2. Un processus gaussien (covariance de Matérn, moyenne linéaire) prédit, pour chaque instant futur, la loi de la meilleure offre attendue : une moyenne µ(t) et un écart σ(t).
3. On choisit le moment t\* où l'utilité espérée de son offre est la plus haute (escompte et goût du risque compris), puis le niveau u\* qui maximise u × P(il accepte u). On concède en ligne droite vers (t\*, u\*), et on recalcule à chaque fenêtre.
4. On génère une offre au hasard autour de la cible ; si la cible passe sous sa meilleure offre, on lui renvoie la sienne.
5. **ECAI 2012** (d'après le résumé) : un fil par adversaire, en parallèle. Les prédictions probabilistes de chaque fil alimentent une seule optimisation qui coordonne les fils. Le gain sur l'état de l'art augmente avec le nombre d'adversaires.

## Ce qui s'applique à l'arène tacto, et ce qui ne s'applique pas

| Idée | Arène tacto | Verdict |
|---|---|---|
| Régression en cours de partie (processus gaussien sur ses offres) | ≤ 10 messages par fournisseur, ~5 réponses en médiane, **2 baisses de prix par fil** en médiane, 5 au 9e décile (X10). Le papier dispose de milliers d'offres | **Ne s'applique pas** : 2 à 5 points, c'est du bruit, et σ resterait énorme |
| Utilité mesurée dans notre propre fonction | `arena_kit.cost.total_cost` donne le C exact de chaque feuille | S'applique, c'est déjà fait (X9, X10) |
| Temps réel, escompte | Tours comptés, pas d'escompte. Le risque, c'est l'`final_offer` puis le départ (P18 : 50 départs sur 57 relances, X9) | Remplacer « temps » par « tour » et « échéance » par « risque de départ » |
| Réponse optimale à une prédiction (u\* = argmax u × P(accepte)) | Applicable **si** la prédiction vient d'ailleurs que de la partie | Garder la règle de décision, changer la source |
| Coordonner des fils concurrents | RFQ à plusieurs fournisseurs (P05, D02) | S'applique (voir plus bas) |

## La version réaliste : un modèle appris hors ligne

Ce qu'on sait du moteur fournisseur (`03 Build/Architecture.md` du vault, 11/10 00:54, sur nos meilleures parties) :
- environ **80 % du score final est déjà dans sa première contre-offre** (P04 100 %, P07 88 %, P05 et P18 79 %, P08 66 %, P11 58 %) ;
- son **plancher**, déduit de `c_best`, va de **74 % à 99 % de son prix d'ouverture** (P05 74, P18 78, P08 84, P07 87, P11 93, P04 99).

Réserves du vault : ce sont des lectures des meilleures parties, pas des lois du moteur.

Donc, au lieu d'apprendre la courbe pendant la partie, on apprend **avant**, sur les sessions exportées : entrée = **sa première contre-offre** (en % de son ouverture) + **le type de fournisseur ou de cas** (but de catégorie, RFQ ou bilatéral, lettre de hausse, capacité, alternative) ; sortie = **le plancher prédit** (son prix le plus bas observé, ou celui qu'implique `c_best`), avec un intervalle. En partie, une seule observation (sa première réponse) suffit à placer le cas sur la courbe apprise. Ensuite, l'étape 3 du papier choisit la cible (u\* = argmax u × P(plancher ≤ u)) au lieu du calendrier fixe `PEGASUS_SCHEDULE` (0, 22, 38, 52 %…).

Lien avec X9 :
- **Le premier mail fixe l'échelle.** À premier mail identique, l'argument décale sa contre-offre de 0,15 à 0,20 €, environ 3 % ; les tours suivants sont parallèles. Le modèle doit donc prendre en entrée l'argument et les feuilles du premier mail, sinon il confond l'effet de notre mail avec le type de fournisseur.
- **Ce qui reste à prendre, en prix** (X9 d'Icham) : l'écart de prix au record, dans la structure du fournisseur, est de **4,4 % sur P08** (5,02 € avec clause contre 5,25 €), **2,8 % sur P18** et **2,3 % sur P10**. C'est l'ordre de grandeur qu'un meilleur plancher prédit peut aller chercher.
- **Ancre** : P18 à 78 % de son prix donne 0,431, à 80 % donne 0,630 ; P10 à 80-85 % déclenche une offre finale immédiate. Un plancher prédit sert aussi à **ne pas ouvrir sous lui**.

## Coordination concurrente appliquée aux RFQ (P05)

P05 : appel d'offres à trois fournisseurs, baisse totale médiane de **20,1 %** par fil (X10), la plus forte des cas. Version ECAI ramenée à l'arène :
- un plancher prédit par fil (même modèle hors ligne), puis **une seule décision** : quel fil pousser, lequel tenir, et quand clore. L'espérance porte sur le *meilleur* accord des trois, pas sur chacun ;
- concrètement : ne pas concéder sur un fil si un autre a une probabilité forte de passer sous notre cible ; citer l'offre vérifiable du rival au fil qui a le plus de marge prédite (L9 du labo moteur, et la règle « rival en 2e place » de la PR #12) ;
- piège déjà vu sur D02 : un fil qui n'a plus rien à dire demande 48 fois de clore sur l'offre de l'autre (R3 dans `03 Build/Expériences.md`). La coordination doit aussi dire **qui attend**.

## Données nécessaires et ce qui existe sur cette machine

Recherche faite le 11/10 à 07:33 (`session_dump`, `exports`, `data/lab`, `sessions`, dans `~/Projets`, `~/ehl-tacto`, `~/dev/projects`) :
- **`analysis/pegasus_data/sessions/`**, suivi par Git : **316 sessions** (D01 152, D02 89, P01 9, P02 10, P03 8, P04 5, P05 7, P07 8, P08 5, P10 9, P11 6, P18 8), 7,9 Mo. Mêmes 316 fichiers dans `hollerau-main`, `hollerau-refonte` et `hollerau-resume`. C'est la base de X10.
- `analysis/session_dump.py` existe (lecture d'une session terminée vers `data/sessions/`), mais `data/sessions/` est **vide ici** : aucun dump local.
- `~/Projets/arena-watch/deals.jsonl` : 2 583 deals publics de toutes les équipes, mais seulement équipe, cas, tours, score et économie. **Pas de trajectoire d'offres** : inutilisable pour la première contre-offre.
- `data/lab` : rien trouvé.
- **Le reste est chez Icham** : les 349 sessions jouées par l'équipe hors archive du dépôt, les 162 sessions de X9 lues par l'API, et le total « 534 exports distincts, 590 à réconcilier » de la Passation.

Peu de cas d'entraînement ont plus de 5 à 10 sessions : le modèle doit être **par type**, pas par cas, sinon il apprend les fournisseurs nommés et ne transfère pas aux cas cachés.

## Comment le mesurer avant de le brancher (critère fixé maintenant)

1. **Hors ligne, en laissant un cas de côté** (leave-one-case-out sur P01-P18 et D01-D02) : on apprend sur tous les cas sauf un, puis on prédit le plancher de celui-là à partir de sa seule première contre-offre.
2. **Référence** : la règle bête « plancher = ratio médian des autres cas × son ouverture ».
3. **Critère d'adoption, écrit avant** : erreur absolue médiane ≤ **2 % du prix d'ouverture**, **et** meilleure que la référence sur **au moins 7 cas sur 10** d'entraînement, **et** jamais au-dessus du plancher réel de plus de 3 % sur un cas (un plancher trop haut fait échouer la négociation, cf. le compromis du facteur 0,975 dans `Décisions.md`). Sinon : on ne branche pas, on garde le calendrier actuel.
4. Si le critère passe : rejeu hors ligne sur le simulateur, puis, **sur décision d'Icham seulement**, une mesure par paires sur l'arène (même mail, avec et sans modèle). Critère de score fixé avant cette mesure : pas de recul > 0,10 sur un cas, gain médian > 0.
5. Ce qui ne se mesure pas hors ligne : l'effet de notre propre cible sur sa réponse (les sessions archivées ont été jouées par d'autres versions). C'est la limite principale, la même que dans X9.
