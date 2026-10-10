**Rejeu mécanique validé ; trois défauts persistent dans la validation des sorties LLM.** Aucun réseau et aucune modification des sources r11b ou du paquet Nevil.

Les 203 archives du manifeste READER_GOLD ont été vérifiées par SHA-256 et rejouées sur r11b avec Nevil activé : 1 076 décisions, zéro exception, zéro violation des contrôles de coût/termes/must-haves, zéro promesse de levier fixe, zéro argument supprimé par `guard`. Les 105 actions accept/walk sont identiques à r10 proposé. La seule action changée par rapport à r11 corrige l'acceptation prématurée de P11 au tour 6 : la négociation continue. D01/D02 sont inchangés par rapport à r11 dans les sorties contrôlées.

READER_GOLD sur 2 859 phrases : TP 567, FP 1, FN 27, précision **99,82 %**, rappel **95,45 %**, exactement r10 proposé. Sur 2 021 formulations normalisées : précision **99,75 %**, rappel **96,17 %**. Les faux planchers issus des mentions de paiement ont disparu. Le corpus reste un corpus de développement annoté par Codex, sans seconde annotation humaine indépendante.

Vérification des quatre corrections :

- `keyword_signals` : métriques revenues au niveau de r10 proposé et reproduction « limite de paiement » corrigée ; zéro `floor_hits` et poursuite de la négociation.
- Clôture P11 : correction confirmée dans l'archive `P11-3ee54cc7c382ca6a.json`, index 11. Aucun passage par `must_close` dans ce rejeu r11b : la présence d'au moins une valeur non proposée le bloque ; les autres critères de clôture restent actifs. `remaining_trade` parcourt les valeurs individuelles des options, sans vérifier leur faisabilité ni les combinaisons. C'est une limite de cette heuristique, pas une nouvelle action défavorable observée.
- Mémoire des arguments : zéro référence nouvellement consommée sans être émise, contre quatre occurrences P11 en r11.
- `inflight` : deux tests concurrents déterministes passent. Pendant `observe(A)` et avant publication, le décideur B voit encore A occupé, tant après une réponse normale qu'après le traitement d'un 409.

Hors P11, une seule décision change ses feuilles, dans P08 : la suppression d'un faux `lead_time_firm` rétablit les alternatives de paiement/index ; le package principal reste 5,15 €/90 jours/24 mois/sans index. Aucun changement d'action.

**Limite pour le lot en cours avec `PEGASUS_READER=1`.** Aucune archive locale des réponses LLM n'est disponible. Le rejeu active le lecteur en mode cache `replay`, interdit tout transport, et rencontre 1 658 absences de cache ; toutes utilisent le repli keyword. Ce résultat valide ce repli, pas les classifications LLM réelles ni leurs effets sur les scores.

Sondes distinctes avec réponses LLM simulées, sans appel réseau :

| Sonde | Résultat r11b | Correction nécessaire |
|---|---|---|
| Sortie `[]`, ou `signals` contenant une chaîne | `AttributeError` ; le test intégré à `agent.decide` échoue aussi après le repli d'`observe` | Valider les types des conteneurs/champs et conserver les signaux keyword en cas de résultat malformé. |
| `cost_floor` associé à la citation exacte « There is no absolute limit on price. » | Signal accepté, alors que les keywords le rejettent | Étendre les exclusions sémantiques au résultat LLM ; `cost_floor` n'est pas protégé par `AFFIRMATIVE`. |
| Ligne « Our price is EUR 54 and our lead time is 28 days. », citation « our lead time is 28 days », signal délai avec valeur 54 | `lead_time_days=54` accepté : 54 existe ailleurs sur la ligne | Relier le nombre à la citation, au champ et à son unité ; sa simple présence sur la ligne ne suffit pas. |

Le contrôle positif « Our firm lead time is 28 days », valeur 28, passe. Les sorties négatives ci-dessus sont des injections de test : elles ne prétendent pas reproduire des réponses LLM observées dans le lot réel. Les deux sondes sémantiques respectent la forme JSON demandée ; la validation du schéma ne les empêche donc pas.

Un défaut secondaire demeure par lecture du code : `st['proposed']` est rempli avant le passage de `guard`, donc une feuille écartée pourrait compter comme proposée. Aucune occurrence dans les 203 archives, puisque `guard` ne rejette aucune feuille. L'enregistrement après validation refléterait mieux ce qui sera envoyé.

Reproduction : `python -m intel.review_round11b` et `python -m intel.review_round11b_probes`. Sources inchangées vérifiées par SHA-256. Réponses fournisseur historiques imposées, PDF remplacés par fixtures ; aucune prédiction de score et aucune nouvelle session practice lancée.

Preuves : [replay complet](../intel/generated/ROUND11B_REPLAY.json), [comparaison](../intel/generated/ROUND11B_REVIEW.json), [gold](../intel/generated/ROUND11B_READER_METRICS.json), [sondes LLM et concurrence](../intel/generated/ROUND11B_PROBES.json).
