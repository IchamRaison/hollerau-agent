# Revue r12e

**GO pour le lot practice demandé.** Snapshot `latest-r12e`, comparaison à r12d ; sources du kit réel et du paquet `hollerau` identiques aux copies examinées avant lancement.

- Corpus figé : 203 archives, 1 076 décisions ; lot E P02/P01/P11 : 18 décisions supplémentaires. Aucune exception, violation technique, promesse de levier fixe, anomalie de garde ou référence mémorisée sans émission. Les 21 violations techniques de r12d ont disparu.
- P02 lot E accepte `offer:70510-5`, à 349,06 / 90 j / index CU : C estimé 2 286 646,74 ; ouverture 2 282 977,10 ; seuil à +0,5 % 2 294 391,99 ; alternative 2 604 227,78. L'acceptation respecte donc la bande demandée. Le score réel ne se déduit pas de ce rejeu.
- Aucun recul des cibles C ni recul de prix hors plafond fournisseur. Le contrôle isolé des offres identiques donne 134,49 → 134,49 → 134,49, au lieu de 134,49 → 134,76 → 134,49 en r12d.
- Mémoire : une observation ne fournit ni drapeau ni valeur ; deux observations fournissent `cb_too_high=True` et chargeback 0.
- Autre changement de clôture : P04 `P04-c8387f214ee53bc5.json` accepte son offre finale égale à l'ouverture, sous l'alternative ; c'est conforme à la nouvelle règle. Aucune acceptation hors bande autorisée ou au-dessus de l'alternative.
- Deux anciennes archives D01 demandent encore une révision après `agreed` : offres à 100 et 10 000 000, très au-dessus de la bande autorisée. Ce comportement préexistant ne concerne pas la correction P02.

Limites : réponses historiques imposées, standards par fixtures faute de PDF, mémoire initialement vierge ; lecteur en cache replay (1 676 absences, repli keyword), aucun appel réseau pendant la revue. Les tests practice utilisent ensuite le kit réel et son lecteur.

Reproduction : `python -m intel.review_round12e`, `python -m intel.review_round12e_probes`, `python -m intel.review_round12e_summary`. Résultats dans `intel/generated/ROUND12E_{REPLAY,TARGETED,PROBES,REVIEW}.json`.

## Lot réel exécuté

Le cache uv était initialement bloqué en lecture seule, avant création de toute session. Après autorisation hors sandbox, la commande demandée a terminé : 10/10 accords, moyenne 0.678178, quota restant 364.

P01 0.941 | P02 0.013 | P03 0.935 | P04 0.860 | P05 0.734 | P07 0.676 | P08 0.659 | P10 0.679 | P11 0.710 | P18 0.575

P02 conclut désormais, mais reste presque nul : score 0,013172, C_deal 2 282 243,76 contre C_open 2 282 867,49, soit seulement 623,73 de gain. Le GO technique ne signifie pas une performance suffisante sur ce cas.

Détails : `intel/generated/ROUND12E_PRACTICE.json` ; journal `/tmp/pegasus-lot-222607.log`.
