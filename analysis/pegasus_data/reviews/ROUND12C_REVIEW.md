**Les six corrections annoncées passent les reproductions locales. Le rejeu technique est propre ; des limites persistent sur la clôture, les échanges qualité, la nouvelle mémoire et l'association des montants LLM.** Aucun appel réseau et aucune modification de r12c ou du paquet Nevil.

203 archives du manifeste READER_GOLD, SHA-256 vérifiés : **1 076 décisions**, zéro exception, zéro violation des contrôles de coût/termes, zéro promesse de levier fixe, zéro rejet par `guard`, zéro référence consommée sans émission. Cinq traces récentes ciblées en supplément : **33 décisions**, mêmes contrôles sans anomalie. Total des deux passages : **1 109 décisions**. Le plancher désactivé pour les deux premières offres reste traité comme un changement volontaire. Les dépassements de cible/plancher observés en r12 ont disparu.

| Correction / cas | Résultat observé |
|---|---|
| P01 | Ouverture **130,46 €/avril 2027/90 jours** dans la fixture. La structure d'ancrage est réellement insérée. Le prix ne reproduit pas les 129 € annoncés : le référentiel replay est reconstitué sans les PDF réels. |
| P08 | Ouverture **24 mois**, 4,84 €/90 jours/sans index. Aucun changement des décisions contre r12. |
| D02 | Retour à **28 jours pour DEMO-J1**, **35 pour DEMO-C1**, au lieu de privilégier un délai raccourci à coût égal. |
| P05 | BAFO reste désactivé ; aucune action accept/walk changée sur le corpus ou la trace récente ciblée. |
| Chargeback zéro | La sonde « We require zero chargebacks » avec une offre courante à 500 € n'émet plus que des feuilles à **0 €**. Le mot `zero` produit bien la valeur 0, même sans nombre ni unité explicites. |
| Répétition | La hausse de 0,4 % a disparu ; les feuilles répétées passent par `_done`. Aucun dépassement de coût introduit par une hausse après calcul. Une action de clôture change, voir ci-dessous. |
| Types et nombres | `quote=42`, `type=[]`, sortie `[]`, élément de signal chaîne : aucune exception. Valeur 54 sur « EUR 54.30 » rejetée ; confusion entre 54 EUR et 28 jours rejetée ; négation de plancher rejetée dans la sonde précédente. |

**Seul changement d'action du corpus : P02, `P02-4b0ac8e9bd9fa05e.json`, tour 4/index 7.** R12c accepte `offer:70510-3`, 372,02 €/90 jours/sans index, où r12 renvoie une contre-offre. Le fournisseur est encore `open`, `floor_hits=0`, `remaining_trade=True`. C'est l'effet de la règle de répétition, qui ne dépend pas de l'épuisement des échanges ni du statut final. L'archive historique obtient 371,92 € sur la réponse suivante, puis accepte. L'écart historique est 0,10 €/unité ; aucun score contrefactuel n'est calculé. Ce changement est un compromis de stratégie à surveiller, pas une violation des contrôles de coût.

Les autres actions accept/walk sont inchangées. Les changements de prix et de structure rendent toutefois les réactions futures inconnues : les réponses historiques imposées ne valident pas un score futur.

**P11 : échange qualité toujours incomplet.** Après les objections sur les chargebacks, la trace ciblée continue de recevoir des feuilles à 300/800 ppm, alors que le fournisseur propose explicitement des prix contre 1 500 ppm. La contrainte chargeback est corrigée ; la sélection de l'alternative qualité n'a pas changé dans ce chemin d'adaptation.

**Nouvelle mémoire : flags effacés au premier email.** Sonde locale : `memory.remember` mémorise `chargeback_too_high` et montant 0 ; `_thread` restaure bien `cb_too_high=True`. La lecture d'un email d'ouverture neutre appelle ensuite `reader.apply`, qui recalcule ce flag depuis `signals_read`, initialement vide, et le remet à False. La première feuille peut donc revenir à chargeback **500 €**, malgré la mémoire zéro. Les flags index/délai/volume/durée suivent la même affectation, contrairement à cash/freeze qui conservent la valeur précédente. Les valeurs numériques restent mémorisées, mais leur flag de contrôle est perdu. Le rejeu principal utilise volontairement une mémoire initiale vierge ; aucune mémoire réelle n'était fournie.

**Lecteur : unité correcte, mauvais champ encore possible.** La sonde JSON conforme au schéma cite « Our floor is EUR 45 » dans la ligne « Our floor is EUR 45 with EUR 150 chargeback », mais donne `cost_floor`, valeur 150. Le lecteur l'accepte encore : il vérifie l'unité sur toute la ligne, sans relier le nombre à la citation ni au champ. Cette sonde ne prétend pas être une réponse LLM réellement observée. La valeur `unit_price` ainsi extraite n'est actuellement pas utilisée pour fixer le prix dans `adapt`; une confusion analogue entre montants pour un champ effectivement utilisé reste à protéger.

READER_GOLD : TP 567, FP 3, FN 27, précision **99,47 %**, rappel **95,45 %**, inchangé par rapport à r12. Pas d'archive LLM locale : 1 719 absences de cache, repli keyword ; le lecteur et Nevil sont chargés, le réseau est bloqué. Les métriques ne valident pas les classifications LLM du lot practice en cours.

Reproduction : `python -m intel.review_round12c`. Le rejeu utilise les fixtures de standards précédentes, ne reconstitue pas le calendrier concurrent et ne transmet aucun message. La mémoire de la sonde est isolée dans un répertoire temporaire. Sources inchangées vérifiées par SHA-256.

Preuves : [corpus complet](../intel/generated/ROUND12C_REPLAY.json), [cinq traces ciblées](../intel/generated/ROUND12C_TARGETED.json), [comparaison et action modifiée](../intel/generated/ROUND12C_REVIEW.json), [sondes corrigées et défaut mémoire](../intel/generated/ROUND12C_PROBES.json), [gold](../intel/generated/ROUND12C_READER_METRICS.json).
