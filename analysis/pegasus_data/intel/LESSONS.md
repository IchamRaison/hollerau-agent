# Enseignements du tour 2

15 exports, dont deux replays P01 identiques. Chaque coup et chaque échange interne est annoté dans `SESSION_ANALYSIS.json` et `sessions/*.md`. Les raisons sont des déclarations, pas des causalités expérimentales.

Claims observés : {'irrelevant': 30, 'verified': 11, 'duplicate': 15}. Les IDs correctement vérifiés n’obligent pas le fournisseur à céder.

## Cibles et leviers calculés

Calculs avec le fichier officiel cost.py, hash dans CASE_PLAYBOOK.json. Options énumérées ensemble, must-haves filtrés, prix arrondis au centime puis C et score revérifiés. Le modèle fournisseur est seulement actif pour stabilise/secure_supply.

| Cas/fournisseur | Termes non-prix de la cible C_best | Prix cible conditionnel | Prix compatible score ≥0,99 (termes si différents) | C cible |
|---|---|---:|---:|---:|
| case:P01/sup:70110 | `{"effective_date": "2027-04-01", "payment_days": 90}` | 138.2 | 138.32 | 1096805.72 |
| case:P02/sup:70510 | `{"payment_days": 90, "index_clause": null}` | 365.8 | 365.99 | 2235511.3 |
| case:P03/sup:70530 | `{"payment_days": 90, "contract_months": 24, "volume_per_year": 4580}` | 428.0 | 428.61 | 3909002.99 |
| case:P04/sup:70620 | `{"payment_days": 90, "contract_months": 12}` | 4.9 | 4.91 | 196331.67 |
| case:P05/sup:70210 | `{"payment_days": 90, "lead_time_days": 28}` | 26.56 | 26.66 | 223369.35 |
| case:P05/sup:70240 | `{"payment_days": 90, "lead_time_days": 35}` | 26.66 | 26.76 | 223373.02 |
| case:P05/sup:70250 | `{"payment_days": 90, "lead_time_days": 28}` | 26.74 | 26.83 | 223417.73 |
| case:P07/sup:70610 | `{"payment_days": 90, "contract_months": 24}` | 5.02 | 5.03 | 299220.8 |
| case:P08/sup:70710 | `{"index_clause": null, "payment_days": 90, "contract_months": 24}` | 5.09 | 5.1 | 958630.24 |
| case:P10/sup:70410 | `{"volume_per_year": 23400, "contract_months": 24, "lead_time_days": 42}` | 28.09 | 28.22 | 1328711.28 |
| case:P11/sup:70140 | `{"ppm_commitment": 1500, "chargeback_eur_per_complaint": 500}` | 43.9 | 43.96 | 722496.0 |
| case:P18/sup:70740 | `{"index_clause": null, "payment_days": 90, "contract_months": 24}` | 4.72 | 4.74 | 222236.48 |

Les impacts de CHAQUE option figurent dans `marginal_term_options` : C, delta contre ancre, détails et must-haves. Les interactions ne sont pas une somme de deltas : toutes les combinaisons sont aussi publiées.

## Limites de la reconstruction de C_best

C_best ne donne qu’une contrainte scalaire. Différents packages, et parfois deux prix pour un même package, satisfont ce coût. En RFQ, C_best porte aussi sur le choix du fournisseur : atteindre ce montant algébriquement chez chaque bidder ne prouve pas qu’il peut l’accepter. `highest_price_package_matching_c_best` et `best_non_price_terms_at_anchor_price` répondent à deux questions différentes : rendre le prix demandé moins agressif, ou minimiser C à prix constant. La cible utilise les meilleurs termes à prix constant si C_best y est atteignable, sinon un autre package compatible, avec le prix le moins agressif.

Le prix d’ouverture est une politique exploratoire explicite (3 % sous la cible, bornée par le prix minimisant C lorsque relationship est actif), pas une loi apprise ni une probabilité de réussite. `plausible_floor` est une hypothèse de prix compatible avec le score, jamais une borne de réserve démontrée. Un minimum mathématique peut être inacceptable pour le fournisseur.

Les standards PDF manquent. Les termes omis viennent du référentiel et des clôtures ; PPM réalisé ≠ engagement. Pour les cas à relationship, le taux est une hypothèse de 8 % faute de paire prix/paiement comparable ; sinon on estime un taux conditionnel en supposant leur valeur cash équivalente. Ce n’est pas un taux caché identifié : une concession commerciale peut expliquer l’écart. Tous sont testés à 4/8/16 %. Le coût central vient du should-cost ; la calibration sur pénalité observée reste conditionnelle au taux et au standard. Les zéros imposent seulement une borne supérieure sur full_cost. P01 retient le scénario bas de l’intervalle parce que la borne supérieure ne peut reproduire C_best : sélection ex post explicite.

Les scénarios should-cost ± erreur et les trois taux sont dans `parameter_sensitivity`. Un score ≥0,99 n’est validé que sous le modèle publié. Si aucun prix ne peut atteindre C_best sous une hypothèse, le fichier expose les racines vides et le minimum, sans inventer un prix.

## Règles à transférer aux fournisseurs inconnus

1. Lire objectifs, horizon, must-haves et champs réellement négociables. Compléter une feuille avec complete_offer, clôturer avec les standards PDF si disponibles, puis calculer C. Une promesse en prose ne modifie pas le contrat.
2. Répondre à tous les fils RFQ avant leur échéance. Trois timeouts consécutifs précèdent plusieurs abandons ; une baisse de prix ne compense pas un fil mort. Garder une offre admissible et une décision de clôture prête.
3. Ouvrir avec un package calculé et une contrepartie réelle ; concessions progressives mesurées en C. Une ouverture très basse n’identifie pas le plancher. La baisse ne suit pas un ratio universel : personnalité, autorité et conditions changent ensemble.
4. Envoyer au plus trois arguments frais, un chiffre par phrase, IDs exacts et fenêtres idx conformes. Ne pas citer sa propre offre dans une phrase de prix : plusieurs messages l’ont transformée en rival_quote irrelevant. Référencer offer_id dans l’action structurée appropriée.
5. Qualité et prévision peuvent être pris en compte (P11/P03) ; OTD est souvent déclaré sans effet. P02/08/10/18 montrent des faits vrais sans changement déclaré du calcul. Choisir une contrepartie accordée à son économie, pas multiplier les doublons.
6. Classer plusieurs sheets par C et supplier_value quand applicable ; garder leurs C proches si on laisse le choix au fournisseur. P01 et P07 montrent une sélection du package avec moins de concession. P18 montre une meilleure alternative finale ignorée.
7. Paiement long réduit le coût buyer ; payer tôt n’est utile que contre une remise compensatrice. Ne pas supposer un lien caché cash-rate égal au buyer. Sur cases stratégiques, recalculer marge cash et relationship avant de proposer un prix très bas.
8. Couvrir l’horizon et comparer fallback/risque. Douze mois peuvent être optimaux si acheter le reste au fallback coûte moins ; 36 mois ne gagnent rien directement par rapport à 24 avec horizon deux ans. Survolume inutile reste acheté.
9. Clause index : calculer path, deadband et index_risk ; base_month ne change pas C dans le code officiel. Un prix nominal moindre avec index peut être plus cher. Proposer prix fixe comme option commerciale, sans croire qu’il est accepté.
10. Demander une fois les coûts et le délai exact au bon rôle ; J1 fournit une annexe, beaucoup de fournisseurs refusent ou donnent seulement une part matière. Le signal open_costing du référentiel ne garantit pas une annexe dans cette session.
11. final_offer observée dès tours 2, 3, 4 ou 5 ; P04 atteint le tour 2 après un timeout et J1 au premier message réel mais tour 3 global. Décider selon statut, validité et C, sans programmer cinq relances obligatoires.
12. Après agreed, les contre-propositions suivantes peuvent réaffirmer l’ancien package. Lire les champs et alternatives à chaque tour. Une phrase commerciale qui contredit la term sheet ne remplace pas ses termes.

## Cas, preuves et erreurs

### case:D02

- C1 agreed tour 1 dans un run reste figé malgré trois sheets ultérieures ; J1 relancé tour 3 fait une final_offer.
- Deux autres runs C1 final_offer tours 4 et 5 ; pas de calendrier universel des concessions.
- J1 abandonné après trois timeouts dans un run ; devis EXW/FCA incomplets pénalisés par défaut.
- J1 fournit un cost-breakdown ; C1 seulement part matière. Les annexes nommées ne donnent pas les chiffres XLSX.
- Une alternative C1 à lead45 viole must-have42 ; contradiction entre prose et termes, les termes bindent.
- [4bdf2705b291e1e9](sessions/D02-4bdf2705b291e1e9.md) : score 0.325207, final_offer [{'round': 5, 'supplier_id': 'sup:DEMO-C1', 'trace_index': 17}], claims {'irrelevant': 2}.
- Offre admissible moins coûteuse observée au tour 3 : `offer:DEMO-C1-3`, C=194938.0 €, gain sur clôture=640.0 €. Disponibilité ultérieure et modèle fournisseur non garantis.
- [9fee8d9d66f3f1f3](sessions/D02-9fee8d9d66f3f1f3.md) : score 0.334971, final_offer [{'round': 3, 'supplier_id': 'sup:DEMO-J1', 'trace_index': 13}], claims {'irrelevant': 4}.
- [ef4175c792b0eb92](sessions/D02-ef4175c792b0eb92.md) : score 0.219747, final_offer [{'round': 4, 'supplier_id': 'sup:DEMO-C1', 'trace_index': 11}], claims {'irrelevant': 3}.
- Offre admissible moins coûteuse observée au tour 3 : `offer:DEMO-C1-3-a`, C=200568.0 €, gain sur clôture=1080.0 €. Disponibilité ultérieure et modèle fournisseur non garantis.

### case:P01

- Les deux sessions à 135,40 sont des replays identiques, pas deux expériences indépendantes.
- Notice 51 jours vérifiée, sans remise démontrée ; multiple sheets choisit 135,80/30j, plus coûteux que 135,40/60j.
- Décaler la hausse réduit le prix payé, mais peut accroître relationship : comparer supplier_value.
- Aucune final_offer observée dans les trois sessions ; coût détaillé refusé malgré signal historique.
- [360a06b60a033bda](sessions/P01-360a06b60a033bda.md) : score 0.582831, final_offer [], claims {}.
- [542fa1f8d903e14c](sessions/P01-542fa1f8d903e14c.md) : score 0.396073, final_offer [], claims {'verified': 1, 'irrelevant': 1, 'duplicate': 1}.
- [a5f7478910f2598a](sessions/P01-a5f7478910f2598a.md) : score 0.582831, final_offer [], claims {}.

### case:P02

- Clause cuivre et calendrier font baisser le prix ; PPM et préavis vérifiés ne changent pas le calcul déclaré.
- Prix 349,36 inférieur au should-cost : relationship observé 112 075,30 €, à intégrer impérativement.
- final_offer au tour 4 ; proposer paiement et clause en packages comparables, pas un prix isolé.
- Calibrer relationship sur le résultat ne révèle pas le véritable cash-rate ni full_cost.
- [30ec723557d102fc](sessions/P02-30ec723557d102fc.md) : score 0.228476, final_offer [{'round': 4, 'supplier_id': 'sup:70510', 'trace_index': 8}], claims {'verified': 2, 'duplicate': 4, 'irrelevant': 2}.
- Offre admissible moins coûteuse observée au tour 3 : `offer:70510-3`, C=2270882.54 €, gain sur clôture=1165.83 €. Disponibilité ultérieure et modèle fournisseur non garantis.

### case:P03

- Tour 1 timeout ; forecast vérifié déclaré pris en compte, OTD déclaré sans effet.
- 432/30j/24m est agreed au tour 2 ; 433,47/60j au tour 3 mérite comparaison de C.
- Après agreed, les demandes suivantes réaffirment le package ancien : ne pas confondre acceptation et dernier sheet.
- 24 et 36 mois couvrent le même horizon de deux ans ; survolume coûte aussi les unités inutiles.
- [31d4c7903569a85a](sessions/P03-31d4c7903569a85a.md) : score 0.773303, final_offer [], claims {'verified': 2, 'irrelevant': 4, 'duplicate': 5}.
- Offre admissible moins coûteuse observée au tour 3 : `offer:70530-3`, C=3972585.74 €, gain sur clôture=12915.6 €. Disponibilité ultérieure et modèle fournisseur non garantis.

### case:P04

- Tour 1 timeout, tour 2 final_offer inchangée 4,96/30j/12m ; aucun claim vérifié.
- 12m laisse 94 000 € au fallback et 4 700 € de risque ; 24m à 4,96 coûte néanmoins davantage.
- Le score nul vient de C_deal=C_open : allonger automatiquement le contrat ne corrige pas le problème.
- [c8387f214ee53bc5](sessions/P04-c8387f214ee53bc5.md) : score 0.000000, final_offer [{'round': 2, 'supplier_id': 'sup:70620', 'trace_index': 4}], claims {}.

### case:P05

- Deux fournisseurs jamais relancés partent après trois timeouts ; l’offre à 32/60j/42j reste sans acceptation.
- 52j initialement interdit par must-have ≤42 ; 42j satisfait le maximum, mais dépasse le besoin de 35j.
- Final_offer tour 4 puis abandon tour 5 : gérer chaque horloge et accepter un package complet admissible.
- Ne pas déduire le meilleur soumissionnaire de la seule offre initiale ; clarifier paiement et délai omis. DAP est déjà fixé par ce cas.
- [0c33c2e26f104a11](sessions/P05-0c33c2e26f104a11.md) : score 0.000000, final_offer [{'round': 4, 'supplier_id': 'sup:70240', 'trace_index': 22}], claims {'irrelevant': 2}.
- Offre admissible moins coûteuse observée au tour 1 : `offer:70240-1-a`, C=267803.98 €, gain sur clôture=None €. Disponibilité ultérieure et modèle fournisseur non garantis.

### case:P07

- Prix par KIT, pas somme libre de prix par pièces.
- Plusieurs sheets acceptés au tour 2 : 5,62/60j/36m ; 5,66/90j n’est pas automatiquement moins coûteux.
- Après agreed, les tentatives de réouverture reviennent au package déjà accepté ; 36m et 24m coûtent pareil dans H=2.
- [1915245dd410385e](sessions/P07-1915245dd410385e.md) : score 0.586131, final_offer [], claims {'irrelevant': 3}.

### case:P08

- OTD et quote concurrente vérifiés déclarés sans effet ; rival à 6,06 révèle une alternative moins bonne.
- Clause inox et durée accompagnent la baisse ; final_offer dès tour 3 à 5,56/60j/24m/db5.
- Index futur positif du cas : aucune clause est moins coûteuse à prix fixe, mais le fournisseur peut la refuser.
- Une variante matière évoquée exige une validation technique et ne constitue pas une offre ferme.
- [ea584a91cc4a0fb7](sessions/P08-ea584a91cc4a0fb7.md) : score 0.411348, final_offer [{'round': 3, 'supplier_id': 'sup:70710', 'trace_index': 6}], claims {'irrelevant': 3, 'verified': 2}.

### case:P10

- OTD et forecast vérifiés déclarés sans effet ; capacité et horizon font passer 32,20 incomplet à 33,80 complet.
- final_offer tour 2 à 33,50/23400/42j/24m ; alternative 36m même C.
- Must-have 22230 minimum ; 19890 et 16379 sont interdits, demander le volume utile sans prime de surachat.
- Le tarif peut augmenter tout en réduisant fortement C : couverture du besoin et retard sont décisifs.
- [cc878c200dad6126](sessions/P10-cc878c200dad6126.md) : score 0.578073, final_offer [{'round': 2, 'supplier_id': 'sup:70410', 'trace_index': 4}], claims {'verified': 2, 'duplicate': 2}.

### case:P11

- PPM vérifié déclaré pris en compte ; ppm300 obtenu sans réduction de prix au tour 1.
- agreed au tour 3 à 46,70/ppm300/cb0 ; qualité protège C, chargeback500 annule defect_cost mais acceptabilité inconnue.
- Paiement60 et volume15900 sont FIXES : promesse de cash rapide ne devient pas une term sheet autorisée.
- Décomposition refusée ; ne pas attribuer causalement la remise au volume déjà fixé.
- [38c0b26db9fb2f5b](sessions/P11-38c0b26db9fb2f5b.md) : score 0.509219, final_offer [], claims {'irrelevant': 4, 'verified': 1, 'duplicate': 3}.

### case:P18

- OTD vérifié déclaré sans effet ; final_offer au tour 2, pas nécessairement après cinq tours.
- Alternative structurée finale 5,70/60j/36m/db5 meilleure que principal 5,70/45j/24m/db3.
- Le fournisseur introduit une clause malgré demande initiale de prix fixe : lire toutes les alternatives.
- Ne pas choisir uniquement le prix nominal ni ignorer index_risk.
- [0fd3bcbc795c0d88](sessions/P18-0fd3bcbc795c0d88.md) : score 0.265153, final_offer [{'round': 2, 'supplier_id': 'sup:70740', 'trace_index': 4}], claims {'irrelevant': 2, 'verified': 1}.
- Offre admissible moins coûteuse observée au tour 2 : `offer:70740-2-a`, C=272611.62 €, gain sur clôture=3332.22 €. Disponibilité ultérieure et modèle fournisseur non garantis.

## Points à débattre avec Claude

- P04 : corriger automatiquement 12m→24m est une mauvaise règle ; voir les coûts au même prix dans le playbook.
- C_best ne révèle pas un plancher unique ; viser 0,99 exige aussi disponibilité et acceptabilité des termes. Les racines et scénarios sont une aide aux demandes, pas la preuve que le bot signera.
- Calibrer un coût caché avec un résultat déjà joué améliore la reproduction de ce cas, pas la prédiction sur un fournisseur inconnu. En finale, remplacer la calibration par données fraîches et intervalle explicite.
