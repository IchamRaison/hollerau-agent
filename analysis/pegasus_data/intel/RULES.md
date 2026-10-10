# Règles de lecture d'un fournisseur inconnu

Règles conditionnelles, issues du package ; ce sont des hypothèses de levier à tester avec des packages alternatifs. La catégorie, le pays et la forme juridique seuls ne suffisent pas.

| Signal observé | À jouer | À éviter | Exemples sourcés |
|---|---|---|---|
| cash_sensitive | Comparer paiement rapide contre baisse chiffrée, avec le coût du capital acheteur. | Allonger les délais ou exiger une baisse sans contrepartie. | sup:70110 : doc:20260902-70110-M2 ; sup:70130 : doc:20260321-70130-M5, doc:20260602-70130-M4 ; sup:70140 : doc:20260710-70140-M2, doc:20260715-70140-M1 |
| margin_protection | Protéger une marge estimée soutenable ; proposer cash, volume réaliste et durée. | Assimiler indice en baisse à une marge réelle disponible. | sup:70130 : doc:20260802-70130-M1 ; sup:70140 : doc:20260715-70140-M1, news:20260911-28 ; sup:70150 : doc:20260804-70150-M4, news:20260809-22 |
| free_capacity | Offrir charge ferme ou regroupement de pièces contre prix et livraison. | Promettre un volume hors besoin ; le surplus est acheté dans C. | sup:70130 : doc:20260602-70130-M4 ; sup:70150 : doc:20260414-70150-M5, doc:20260419-70150-M3 ; sup:70170 : news:20260420-09 |
| capacity_tight | Demander allocation et calendrier contre engagement ferme et durée couvrant le besoin. | Menacer ou imposer un délai irréalisable ; vérifier qualification d'une alternative. | sup:70220 : doc:20260915-70220-P09, news:20260320-04 ; sup:70240 : doc:20260924-70240-M1, news:20260710-18 ; sup:70290 : doc:20260315-70290-M1, doc:20260619-70290-M3 |
| outdated_cost_view | Présenter une ou deux variations d'indices pertinentes et demander une décomposition. | Empiler des indices sans poids ou utiliser une fenêtre trop ancienne pour l'API. | sup:70110 : doc:20260824-70110-M1, doc:20260909-70110-M4 ; sup:70210 : doc:20260908-70210-M1 ; sup:70230 : doc:20260724-70230-M1 |
| hedged_inputs | Demander date de fin de couverture et transition ; négocier base et extras. | Appliquer la baisse spot à des achats déjà couverts ou indexer deux fois. | sup:70190 : doc:20260623-70190-M1, news:20260426-10 ; sup:70520 : doc:20260620-70520-M1, doc:20260701-70520-M4 ; sup:70560 : doc:20260617-70560-M1, quote:7300014 |
| price_frozen | Chiffrer paiement, incoterm, outillage, flexibilité et couverture complète dans C. | Insister sur le prix malgré le gel ; volume/durée ne prouvent pas une exception. | sup:70420 : doc:20260823-70420-M1, quote:7300055 ; sup:70530 : doc:20260826-70530-M1, quote:7300003 ; sup:70540 : doc:20260906-70540-M1, quote:7300067 |
| approval_ladder | Demander qui approuve et transmettre plusieurs packages avec contreparties. | Supposer que l'interlocuteur peut valider une concession importante immédiatement. | sup:70410 : doc:20260310-70410-M1 ; sup:70420 : doc:20260302-70420-M2 ; sup:70440 : doc:20260524-70440-M2 |
| account_exit | Comparer l'alternative et la continuité de service ; envisager une sortie si C l'indique. | Supposer qu'il veut conserver le compte ; révéler l'absence d'alternative. | sup:70580 : doc:20260926-70580-M1, news:20260327-07 ; sup:70620 : doc:20260706-70620-M1, doc:20260917-70620-M4 ; sup:70650 : doc:20260602-70650-M4, doc:20260817-70650-M1 |
| volume_focus | Proposer durée et volume compatibles avec le besoin, comparer le coût non couvert. | Conclure trop court ou suracheter pour une réduction de prix. | sup:70130 : doc:20260322-70130-M6, doc:20260911-70130-M3 ; sup:70260 : doc:20260522-70260-M3 ; sup:70270 : doc:20260223-70270-M2 |
| relationship_memory | Reconnaître les engagements passés et proposer une contrepartie concrète. | Traiter l'historique comme un droit automatique à une nouvelle remise. | sup:70110 : doc:20260715-70110-M5, doc:20260917-70110-M3 ; sup:70120 : doc:20260719-70120-M1 ; sup:70170 : doc:20260512-70170-M2 |
| open_costing | Demander le détail matière/conversion et les taux avant de choisir les arguments. | Confondre modèle should-cost allemand et coût exact de l'usine. | sup:70150 : doc:20260418-70150-M2 ; sup:70230 : doc:20260809-70230-M3 ; sup:70260 : doc:20260212-70260-M1 |
| buyer_late_payment | Corriger la crédibilité de paiement et comparer un package de règlement fiable. | Présenter nos retards comme une faute fournisseur ou promettre sans engagement. | sup:70210 : doc:20260504-70210-P ; sup:70230 : doc:20260812-70230-P ; sup:70250 : doc:20260818-70250-P |
| quality_delivery_red | Demander plan 8D, PPM réaliste et chargebacks ; chiffrer qualité dans C. | Moyenner plusieurs trimestres glissants comme observations indépendantes. | sup:70140 : sc:70140@2026Q3 ; sup:70150 : sc:70150@2026Q3 ; sup:70170 : sc:70170@2026Q3 |
| conflicting_capacity | Faire préciser atelier, date et pièce avant de négocier la charge. | Choisir arbitrairement le signal le plus favorable. | aucun exemple actuel ; règle conservée pour une release future |

## Utilisation dans une négociation

1. Lire déclencheur, notes récentes, devis et clauses ; vérifier qualification et marge estimée.
2. Choisir peu d'arguments pertinents : trois contrôles au maximum par message, un argument par phrase.
3. Une fenêtre d'indice citable utilise deux IDs de la même série, au plus douze mois, fin récente ; ne pas citer la baisse depuis 2022 comme argument vérifié.
4. Proposer plusieurs term sheets avec contrepartie réelle ; chaque feuille couvre tous les champs négociables.
5. Calculer C avec les besoins, horizon, fallback, risques et must-haves du cas ; estimer la marge en cash si stabilise/secure_supply.
6. Rechercher les signaux opposés, les couvertures de matières et les décisions du siège avant d'insister.
7. Ne pas envoyer automatiquement tous les IDs du dossier : doublons, divulgation de devis privés et pertinence ont des conséquences.
