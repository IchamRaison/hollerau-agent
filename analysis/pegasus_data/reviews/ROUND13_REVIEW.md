# Revue r13 : NO-GO, clôture récursive

Rejeu hors réseau de 390 archives (386 sessions locales et 4 sandbox), 2 146 décisions tentées. Aucun paquet effectivement retourné sous son plancher relationnel modélisé ; aucun paquet envoyé à un C estimé supérieur ou égal au minimum de l'ouverture et de l'alternative. La suppression de l'exemption des premières offres corrige le contournement du compteur r12f.

## P02 lot G et boucle de clôture

Trace locale : `arena-data/sessions/P02-cd6c947234ce798d.json`. Les offres restent au-dessus de leur plancher. Le rejeu accepte même l'offre historique au deuxième tour ; les tours suivants sont donc un contrôle conditionnel des réponses enregistrées, et non une trajectoire prédite.

Aux traces 7 et 9 (tours acheteur 4 et 5), la contre-offre de `_accept_best` appelle `_send`. Lorsque le paquet répète le précédent et que le fournisseur ne bouge plus, `_send` appelle `_done`, qui rappelle `_accept_best`. Le même cycle se répète sans envoyer de message ni changer le fil. Il faut éviter cette réentrée : construire une contre-offre sans passer par la logique de clôture de `_send`, ou décider d'une action terminale lorsqu'aucune nouvelle contre-offre acceptable n'existe.

Six occurrences dans le corpus : P02 lot G deux fois ; P02 lot F (`P02-eff3ade3dfb2ed63.json`, trace 9) ; P02 `P02-d9b2cd2c6ad05c51.json`, trace 7 ; deux anciennes fixtures D01 aux offres extrêmes. Le banc interrompt les cycles à quatre appels imbriqués. Un contrôle supplémentaire sans cette garde, sur P02 lot F, confirme un vrai `RecursionError` (limite Python abaissée à 160 pour accélérer le constat). Sur ce rejeu du lot F, aucun accord contrefactuel antérieur ne rend l'erreur inatteignable.

## Messages sans offre

183 messages sans term sheet et sans action subsistent : 118 sur D02, 65 sur P05. Tous sont des messages de coordination RFQ pendant l'examen des autres offres ; aucun ne vient du remplacement d'une contre-offre P02 par une question vide. Sur P02, la nouvelle régression est le cycle de clôture, qui empêche la décision de revenir.

## Autres limites du changement

- Six paquets P02 dépassent encore le C de la meilleure offre fournisseur. `price_for` retourne le prix du minimum du U lorsque le C demandé est impossible : comparer ce prix au plancher ne détecte pas l'impossibilité. Exemple : 359,59 / 60 j / index CU 5 % donne C=2 252 155,51, contre 2 251 827,28 côté fournisseur. Vérifier explicitement le C du paquet retenu après application du plancher. Tous ces paquets restent cependant sous le C d'ouverture et de l'alternative.
- Aucun argument `po:` émis. Le filtrage intervient après `remember` et après limitation du nombre d'arguments : 98 décisions mémorisent des références sans les émettre. Filtrer les candidats avant sélection et mémorisation évite aussi de consommer des places avec des arguments supprimés.

Limites : réponses historiques imposées ; fixtures de standards à la place des PDF ; mémoire initialement vierge ; lecteur en mode replay sans archive LLM dans le banc, repli keyword. Aucun score r13 n'est prédit, aucun appel réseau ni nouvelle session practice.

Résultats : `intel/generated/ROUND13_REPLAY.json`, `ROUND13_REVIEW.json`, `ROUND13_TARGETED.json`, `ROUND13_RECURSION.json`. Reproduction : `python -m intel.review_round13 targeted`, puis les trois partitions `python -m intel.review_round13 0`, `1`, `2`.
