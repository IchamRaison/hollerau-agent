**NO-GO en l'état pour le lot P05, P07, P18, P08, P02, P10.** Les blocages sont la perte des protections sémantiques du lecteur et la clôture sans vérification des échanges encore possibles. L'adaptateur de Nevil passe les contrôles locaux ; le désactiver ne corrige pas ces blocages.

Rejeu entièrement local du 10 octobre 2026 : les 203 archives du manifeste READER_GOLD, 1 076 décisions par mode, `PEGASUS_TEAM_CLAIMS=1` puis `0`, adaptateur réellement chargé sous `hollerau`. Douze archives ne contiennent pas de décision acheteur rejouable. Aucun appel réseau, transports bloqués, reader/prose LLM désactivés. Sources des deux paquets inchangées par SHA-256.

Résultats dans les deux modes : zéro exception, zéro violation des contrôles de coût/termes/must-haves, zéro promesse portant sur un levier fixe, zéro argument supprimé par `guard`. Les contrôles supplémentaires ne trouvent aucune feuille contredisant les contraintes observées d'index, de délai ou de chargeback dans ces archives. Les offres et actions sont identiques entre les deux sélecteurs d'arguments, avec 59 décisions dont les références changent. Les réponses historiques sont imposées : cela ne valide ni les réactions futures ni les scores.

Le gold, figé avant r11, donne sur 2 859 phrases : TP 567, FP 25, FN 27, précision **95,78 %**, rappel **95,45 %**. La proposition r10 donnait TP 567, FP 1, FN 27, précision **99,82 %**. Sur 2 021 formulations normalisées : TP 402, FP 16, FN 16, précision et rappel **96,17 %**. Le corpus reste un corpus de développement annoté par Codex, sans deuxième annotation humaine indépendante.

Les 24 nouveaux faux positifs sont : 18 demandes de justificatifs de volume interprétées comme demandes d'engagement, 2 délais encore à confirmer interprétés comme délais fermes, 4 `cost_floor` (deux formulations proches d'une limite et deux variantes d'une limite de paiement). `reader.keyword_signals` a conservé les regex de r10 proposé, mais retiré le découpage en phrases et les exclusions sémantiques. Les négations synthétiques « no absolute limit », « no free capacity », « chargeback is not too high » produisent également des signaux positifs.

**Clôture : une régression réelle du rejeu.** Dans `P11-3ee54cc7c382ca6a.json`, tour 6, index 11, r11 accepte `offer:70140-5` à 45,50 €/300 ppm/chargeback 0 ; r10 et r10 proposé continuent la négociation. Le dernier email évoque encore 45,00 € contre 1 500 ppm. `remaining_trade` n'inclut pas le levier qualité ; il se limite aux flags demandés, et ne cherche pas les structures faisables non essayées. Le statut fournisseur est encore `open`. L'archive historique atteint ensuite 0,7935, mais aucun score contrefactuel n'est attribué à r11.

Treize passages par `_done` satisfont `must_close` : onze sur D02 déjà en `final_offer`, deux sur P11, dont un seul change l'action. Dans les six cas du lot demandé, aucune action accept/walk ne change sur les archives ; le problème reste général et susceptible de se manifester dans les nouvelles sessions.

Une reproduction synthétique indépendante confirme le danger du lecteur : première offre à 20 avec « 30 days is our absolute limit », deuxième offre à 18 avec la même limite de paiement, statut `open` ; r11 compte deux `cost_floor` et accepte immédiatement. Aucune limite de prix n'a été exprimée. Par ailleurs, `trade_offered` est un booléen global : une adaptation passée sur un levier suffit à déclarer épuisé un nouveau levier demandé plus tard. Le seuil 2/3 est implémenté, mais « échange restant » n'est pas réellement calculé.

Comparaison des arguments, Nevil contre sélection historique r11 avec `TEAM_CLAIMS=0` :

| Cas | Nevil | Différence / appréciation |
|---|---|---|
| P01 | Préavis 51/90 jours, retard fournisseur, énergie en baisse | Préavis plus explicite ; supprime le should-cost susceptible de renforcer le fournisseur. |
| P02 | Prévision +11,9 % seulement | Retire OTD 90,4 % et commandes historiques ; sélection plus prudente mais réservoir très réduit. |
| P03 | Commandes 400,19 → 412,74 €, prévision +10,3 % | Retire should-cost et OTD ; factuel, efficacité commerciale non mesurable au replay. |
| P04 | Commandes 4,29 → 4,39 € | Retire prévision +4,2 % et OTD ; moins d'arguments faibles. |
| P05 | Offre concurrente, qualité/OTD selon destinataire, énergie | Pas d'offre propre citée comme rivale, ni de scorecard d'un autre fournisseur dans les sorties contrôlées. |
| P07 | Prévisions des quatre composants | Retire commandes de composants non comparables au prix du kit ; cohérent. |
| P08 | Commandes historiques et lettre de couverture matière jusqu'en mars 2027 | Ajoute l'argument de couverture ; retire faible croissance et OTD. |
| P10 | Commandes à 29,89 €, should-cost 24,31 € | Retire la croissance +10,1 % dans le contexte de capacité ; cohérent. |
| P11 | Qualité 2 376 ppm, OTD 78 % d'un autre trimestre, énergie | Retire la croissance de l'ouverture ; amélioration de priorité, mais défaut de mémoire ci-dessous. |
| P18 | Commandes 5,26 → 5,84 € | Retire prévision +1,9 % et OTD ; réservoir réduit, sans argument erroné détecté. |
| D01/D02 | Identiques à l'ancien sélecteur | Aucun effet mécanique de l'adaptateur ; aucune conclusion nouvelle sur leurs scores. |

Le nombre de références émises Nevil/ancien sélecteur, cumulé sur les archives, est P05 38/41, P07 20/55, P18 10/40, P08 9/24, P02 5/50, P10 12/28. Il ne s'agit pas de nombres d'arguments : un seul argument peut citer plusieurs références. Un appel direct des familles de l'adaptateur sur tous les cas disponibles n'émet aucun warning/échec de repli.

Autres défauts constatés :

- `remember` précède `claims_cap` : dans quatre archives P11, `fc:310020@2026-09` est consommé en mémoire sans être émis. Appliquer le plafond avant d'enregistrer, et enregistrer seulement les références effectivement envoyées.
- Le durcissement r10 de `reader.read` manque aussi : une réponse LLM simulée `[]` produit `AttributeError`. `observe` intercepte l'erreur, mais la relecture dans `decide` peut la refaire sous verrou. Aucun appel LLM réel n'a été exécuté.
- Lecture statique de `play.py` : `inflight.discard(dsid)` précède `observe`, puis la publication de la réponse dans `threads`. Pendant l'observation hors verrou, un autre fil peut choisir une ancienne offre du fournisseur qui n'est déjà plus marqué occupé. Garder `inflight` jusqu'à la publication atomique de la réponse. Ce risque concurrent n'est pas quantifié par le replay séquentiel.
- Si le filtre `adapt.pick_sheets` ne trouve aucune structure, `_sheets` poursuit avec la sélection historique : une contrainte peut ainsi être relâchée dans un cas nouveau. Aucun contre-exemple dans les archives contrôlées. Exemple de bord à protéger : chargeback fournisseur déjà à zéro, filtre strictement inférieur à zéro impossible.

Avant GO : réintégrer le `keyword_signals` complet de r10 proposé et sa validation des réponses LLM, calculer les échanges faisables encore non proposés avant clôture (qualité comprise), garder le fournisseur occupé jusqu'à publication de sa réponse ; déplacer l'enregistrement des arguments après le plafond. Ne pas remplacer ces corrections par `TEAM_CLAIMS=0` : les deux modes ont la même clôture prématurée.

Reproductibilité : `python -m intel.review_round11 1` puis `python -m intel.review_round11 0`. Le loader compile les sources fournies sans les modifier, fournit les standards par fixtures textuelles car les PDF ne figurent pas dans les exports, et précharge les observations keyword avant la décision. Le calendrier concurrent/busy n'est pas reconstructible depuis ces archives.

Preuves : [synthèse et reproductions](../intel/generated/ROUND11_REVIEW.json), [replay Nevil](../intel/generated/ROUND11_REPLAY_TEAM1.json), [replay ancien sélecteur](../intel/generated/ROUND11_REPLAY_TEAM0.json), [métriques gold](../intel/generated/ROUND11_READER_METRICS.json), [harness](../intel/review_round11.py).
