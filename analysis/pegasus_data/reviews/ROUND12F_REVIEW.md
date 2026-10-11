# Revue r12f : NO-GO avant correction du compteur

Les exports P01/P02 du lot F ne sont pas présents localement au moment de cette revue. Aucun appel réseau ni nouvelle session practice. Rejeu des 19 archives P01/P02 disponibles : 86 décisions, aucune exception ; rejeu ciblé supplémentaire du lot E : 11 décisions.

## Contournement du plancher reproduit

Dans `agent.py`, le traitement d'un `agreed` précoce remet `st['offers']` à zéro (ligne 348). `_floored` utilise ce même compteur pour dispenser les deux premières offres de plancher. L'appel ajouté dans le wrapper `decide` conserve donc cette exemption, même après la troisième offre réelle.

Sur `arena-data/sessions/P02-1772c59e0947ba39.json`, trace 5, troisième offre réelle : compteur interne 2 ; prix 329,54 pour un plancher 355,93 (14 j, index CU 5 %), et 332,15 pour un plancher 356,01 (14 j, sans index). La demande fournisseur est 358,95, donc le plafond fournisseur ne justifie aucune de ces deux baisses. La proposition 90 j à 337,80 est aussi sous le plancher plafonné à la demande fournisseur (358,95).

Un contrôle isolé d'un accord précoce P02 confirme le mécanisme : deux offres déjà envoyées, `agreed`, compteur ramené à 1, troisième offre à 333,14/330,91/330,47, toutes sous le plancher plafonné à 347,12.

Correction nécessaire : compter cumulativement les offres réellement envoyées, sans réinitialiser ce compteur lors d'un accord précoce ; conserver éventuellement un compteur distinct pour le calendrier de concessions. Un test fondé sur `st['offers']` seul ne vérifie pas la troisième offre réelle ; le banc r12f compte donc aussi les messages acheteur portant des term sheets.

## Correctifs vérifiés

- Wrapper avec compteur 3 : offre P02 à 344 relevée à 359,59.
- Même coût légèrement supérieur à l'ouverture : `final_offer` accepté dans la bande ; `agreed` renvoyé en négociation avec marge normale.
- PRIOR_MIN=3 : observations 1 et 2 sans drapeau ni valeur ; observation 3 active les deux.
- ANCHOR_FLOOR=0,92 chargé ; ouverture P01 lot E à 123,73 avril/90 j dans les fixtures. Aucun score r12f déduit de ce rejeu.
- Fichier de mémoire du kit réel absent ; snapshot et kit réel identiques lors de la vérification.

Résultats : `intel/generated/ROUND12F_REPLAY.json`, `ROUND12F_TARGETED.json`, `ROUND12F_PROBES.json`. Reproduction : `python -m intel.review_round12f`, `python -m intel.review_round12f_probes`.

Limites : réponses fournisseur historiques imposées, PDF remplacés par fixtures ; lecteur sans réseau, cache absent dans le banc (97 lectures en repli keyword). Le lot F lui-même n'a pas été rejoué faute d'export.
