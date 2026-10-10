# Tour 10 — Lecture des réponses et adaptation

Jeu livré : **2859 phrases fournisseur exactes**, **2021 formulations normalisées**, 203 archives (`sessions` et `sandbox-ab`). Chaque phrase, y compris signatures et lignes sans signal, porte 0..n types et ses provenances. Les emails des threads, ouvertures, réponses et raisons de trace sont couverts.

Les annotations sémantiques sont explicites dans `intel/reader_gold.py`, établies par Codex sur le catalogue, indépendamment des sorties de keyword_signals ; aucune seconde annotation humaine indépendante. Chiffres/ellipses sont regroupés pour l’annotation puis développés dans les phrases exactes. Les définitions, conventions et sources SHA256 sont dans [READER_GOLD.json](../intel/generated/READER_GOLD.json).

Les regex sont développées sur ce corpus : **mesures descriptives, pas une performance hors échantillon**. Les tests comprennent aussi négations, fausses citations et cas synthétiques à IDs inconnus. La provenance email/trace/raison est conservée ; les duplications ne pondèrent pas les résultats.

## Précision / rappel du repli

| Vue | Repli initial P / R | Repli proposé P / R |
|---|---:|---:|
| Phrase exacte | 92.9 % / 35.2 % | 99.8 % / 95.5 % |
| Formulation normalisée | 94.5 % / 36.8 % | 99.8 % / 96.2 % |

| Type | Phrases positives | Initial P / R | Proposition P / R |
|---|---:|---:|---:|
| wants_faster_payment | 264 | 100.0 % / 36.0 % | 99.6 % / 92.4 % |
| wants_volume_commitment | 95 | 64.7 % / 23.2 % | 100.0 % / 96.8 % |
| wants_longer_contract | 34 | 100.0 % / 17.6 % | 100.0 % / 88.2 % |
| requires_index_clause | 21 | 100.0 % / 61.9 % | 100.0 % / 100.0 % |
| price_frozen | 14 | 100.0 % / 85.7 % | 100.0 % / 100.0 % |
| needs_internal_approval | 3 | 100.0 % / 100.0 % | 100.0 % / 100.0 % |
| arguments_rejected | 44 | 100.0 % / 47.7 % | 100.0 % / 100.0 % |
| chargeback_too_high | 2 | 100.0 % / 100.0 % | 100.0 % / 100.0 % |
| lead_time_firm | 83 | 100.0 % / 21.7 % | 100.0 % / 100.0 % |
| capacity_tight | 2 | 100.0 % / 100.0 % | 100.0 % / 100.0 % |
| free_capacity | 2 | 100.0 % / 100.0 % | 100.0 % / 100.0 % |
| cost_floor | 30 | 76.5 % / 43.3 % | 100.0 % / 100.0 % |

Principales corrections : paiement associé à un bénéfice explicite, question de volume réellement à attribuer, durée avec planning security, index obligatoire dans les deux ordres de phrase, earliest/shortest/firm lead time, données déjà intégrées et rejetées. Les remerciements de volume seul, validation déjà faite et proximité d’un plancher ne deviennent pas une contrainte.

Les erreurs restantes sont intégralement conservées dans [READER_METRICS.json](../intel/generated/READER_METRICS.json), sans les masquer. Les types rares (capacity/chargeback/free_capacity/approval) ont seulement 2–3 phrases positives : aucune conclusion de fiabilité générale sur leur taux.

Le chemin LLM a été testé avec réponses factices : citation sensible à la casse sur la ligne citée, rejet des références absentes/types inconnus/formats malformés et repli sur panne. **Une citation existante prouve sa provenance, pas la justesse sémantique du type choisi par le LLM** ; un test montre qu’un type erroné cité sur “Hallo” reste possible. Aucun appel LLM réel.

## Règles concrètes

L’agent appelle reader.read puis reader.apply sur le dernier email fournisseur, une fois par texte distinct. Aucun texte acheteur ni raison/backoffice caché n’oriente le runtime. Les drapeaux sont cumulatifs selon le contrat de reader.apply ; une nouvelle phrase sans signal ne supprime pas une ancienne demande.

| Signal | Drapeau | Modification suivante | Appui et limite |
|---|---|---|---|
| wants_faster_payment | cash | Ajouter le paiement rapide autorisé au même C, avec échange explicite contre le prix ; ne pas modifier un paiement fixe. | P05 : 30,50 → 28,77/14 j au tour 2 ; D02 exprime régulièrement que le cash aide. L’existence de la remise ne mesure pas l’effet de notre nouvelle phrase. |
| wants_volume_commitment | wants_volume | Toutes les offres négociant le volume couvrent le besoin annuel entier ; engagement ferme chiffré et distinction avec le forecast. | P02/P18 demandent encore quel volume est commis ; P10 récompense un volume complet avec la durée. Un forecast isolé ne devient pas une promesse de release schedule inventé. |
| wants_longer_contract | wants_duration | Proposer la première durée autorisée au-delà de la durée debout, ou maintenir la durée maximale ; seulement si C/must-haves le permettent. | P08 passe de 12 à 24 m entre les lots et améliore fortement le résultat ; P10 attribue une baisse de 0,30 € au terme étendu. Aucune durée codée par cas. |
| requires_index_clause | wants_index | Reprendre uniquement la série autorisée citée par le fournisseur ; contraindre toutes les offres à cette famille et demander une baisse de base. Sans famille identifiée : question ciblée. | P18/P08 disent ne pas pouvoir fixer les prix sur la durée et imposent AS-14404 ; P02 explique une base réduite avec CU-NOTATION. Le cadeau d’index peut néanmoins dégrader C : les mêmes bornes de coût restent exigées. |
| price_frozen | freeze | Supprimer une proposition de prix inférieur à termes identiques ; conserver les offres sur des termes réellement différents, ou demander un package faisable. | P03 bloque les réductions mais accepte de négocier paiement/durée/date. Un gel de la base ne prouve pas que tout prix total avec d’autres termes est impossible. |
| needs_internal_approval | needs_approval | Demande unique au commercial manager dans le contre-mail prévu, avant la finale ; confidentialité et approbation déjà terminée ne déclenchent plus cette demande. | P05 : circuit interne “give the rest of the step”, meilleur bidder agreed au tour 2. Le lecteur distingue le besoin de validation d’un refus de cost breakdown corporate. |
| arguments_rejected | args_rejected | Au plus un nouvel argument cité ; recentrer le message sur les termes. Les IDs sélectionnés mais non envoyés restent disponibles. | Price history : douze réponses sans effet dans les cas faibles au tour 9 ; plusieurs fournisseurs réaffirment que la donnée est déjà intégrée. Ne pas supprimer automatiquement toutes les catégories futures. |
| chargeback_too_high | cb_too_high | Chaque package plafonne le chargeback au niveau de l’offre fournisseur courante ; pas de valeur privée ni baisse sous zéro. | P11 réduit explicitement un chargeback jugé excessif. Le plafond vient de sa feuille structurée, pas d’un nombre extrait librement d’un mail. |
| lead_time_firm | lead_firm | Chaque package conserve au moins le délai fournisseur courant, sur une option légale ; si les must-haves ou C rendent ce choix impossible, question sans feuille. | P05/D02 répètent l’earliest lead time ; P10 refuse les accélérations qui demandent du premium et confirme 54→56 j légal. Le coût de retard est conservé. |
| capacity_tight | capacity_tight | Reconnaître la contrainte et demander que le volume/durée fermes la valorisent ; aucune promesse de capacité inventée. | P10 indique une utilisation élevée et refuse la compression du délai ; l’ancre capacité r10 existe déjà. Ce signal seul ne prouve pas un délai absolu. |
| free_capacity | free_capacity | Demander une amélioration pour l’attribution de capacité au volume réellement proposé ; aucune règle numérique de rabais automatique. | D02 dit disposer de capacité libre. Le levier est commercial ; aucun prix de réserve privé ne s’en déduit. |
| cost_floor | cost_floor | Prêt à conclure ; clore un prix open qui stagne après deux contres uniquement sans levier signalé négociable ni changement faisable de termes encore inédit. Les contrôles C/alternative/ouverture et IDs restent ceux de r10. | D01/D02 expriment un bottom line ; P03 distingue le gel de prix et les autres termes. “Proche de la limite” et limite de paiement ne sont pas un plancher de prix. |

Exemples verbatim du gold, avec provenance :

- `wants_faster_payment` : « … days payment is good, cash is tight here. » — [case:P05 / reason](../arena-data/sessions/P05-51ffeb39e0bbf1ed.json) ; phrase `04a2786cf57e7c98`.
- `wants_volume_commitment` : « Which volume can you commit to? » — [case:D01 / trace_email](../arena-data/sessions/D01-0e1b2b284a317b55.json) ; phrase `78c98ea0e008912f`.
- `wants_longer_contract` : « In exchange for this extended duration, we reduce the unit price to €…. » — [case:P10 / reason](../arena-data/sessions/P10-cc878c200dad6126.json) ; phrase `c6f2f98628339ff5`.
- `requires_index_clause` : « Therefore, we must maintain our offer of €… per unit subject to the CU-NOTATION index clause. » — [case:P02 / reason](../arena-data/sessions/P02-d9b2cd2c6ad05c51.json) ; phrase `3a85e124c29806ad`.
- `price_frozen` : « We see your figures, but we cannot give up margin right now. » — [case:P11 / trace_email](../arena-data/sessions/P11-38c0b26db9fb2f5b.json) ; phrase `00ddccb6159597ee`.
- `needs_internal_approval` : « We need to clarify this internally - we will come back to you on price. » — [case:D02 / trace_email](../arena-data/sessions/D02-054ced28f8e6b368.json) ; phrase `64735fbe6d63ba09`.
- `arguments_rejected` : « That does not change our position. » — [case:P04 / trace_email](../arena-data/sessions/P04-36f322d6faf8f103.json) ; phrase `42325a09f8cb9ac7`.
- `chargeback_too_high` : « I picked your … ppm package but … EUR chargeback is way too much, so I changed it to … EUR. » — [case:P11 / reason](../arena-data/sessions/P11-c168282558ca273e.json) ; phrase `c20ed2d8c046fa02`.
- `lead_time_firm` : « With overtime we can deliver in … days, at a premium. » — [case:D02 / reason](../arena-data/sessions/D02-054ced28f8e6b368.json) ; phrase `4623432ac7f24d5a`.
- `capacity_tight` : « Given our high capacity utilization, we must maintain the lead time at … days to ensure reliable delivery. » — [case:P10 / reason](../arena-data/sessions/P10-ae99ef2ade741473.json) ; phrase `d5b6c27cebefc395`.
- `free_capacity` : « We have free capacity for your parts. » — [case:D02 / trace_email](../arena-data/sessions/D02-054ced28f8e6b368.json) ; phrase `dcc7862e7bed5e51`.
- `cost_floor` : « this is our last price, take it or leave it. » — [case:D02 / trace_email](../arena-data/sessions/D02-054ced28f8e6b368.json) ; phrase `dfdccc188918f5df`.

## Cas dont les messages changent réellement

Comparaison à latest-r10 sans narration/LLM. Le compteur porte sur les instants acheteur de toutes les archives ; les différents historiques ne sont pas des essais indépendants du nouveau comportement.

| Cas faible | Décisions | Textes changés | Feuilles changées | Actions changées | Essai practice justifié ? |
|---|---:|---:|---:|---:|---|
| P05 | 44 | 21 | 13 | 0 | Oui, message réellement différent |
| P07 | 18 | 12 | 11 | 0 | Oui, message réellement différent |
| P18 | 23 | 16 | 13 | 0 | Oui, message réellement différent |
| P08 | 13 | 10 | 5 | 0 | Oui, message réellement différent |
| P02 | 24 | 19 | 15 | 0 | Oui, message réellement différent |

La même différence existe sur la dernière archive de chacun des cinq cas :

| Cas | Dernière archive | Textes changés | Feuilles changées |
|---|---|---:|---:|
| P05 | [P05-51ffeb39e0bbf1ed.json](../arena-data/sessions/P05-51ffeb39e0bbf1ed.json) | 8 | 4 |
| P07 | [P07-0b18b19250fe83d1.json](../arena-data/sessions/P07-0b18b19250fe83d1.json) | 2 | 2 |
| P18 | [P18-9ce11ac5f56f8ae3.json](../arena-data/sessions/P18-9ce11ac5f56f8ae3.json) | 3 | 2 |
| P08 | [P08-2fc3680889612cdf.json](../arena-data/sessions/P08-2fc3680889612cdf.json) | 4 | 1 |
| P02 | [P02-f712b5035de4e93e.json](../arena-data/sessions/P02-f712b5035de4e93e.json) | 4 | 1 |

### P05 : exemples appariés

- `arena-data/sessions/P05-0c33c2e26f104a11.json`, index 9, sup:70240, tour 2 : texte=True, feuilles=True, action=False.
  - Retrait : We are happy to pay faster if that helps your cash flow, in exchange for a better price.
  - Avant : `[{"terms": {"unit_price": 26.69, "payment_days": 90, "lead_time_days": 35}}, {"terms": {"unit_price": 26.69, "payment_days": 90, "lead_time_days": 28}}, {"terms": {"unit_price": 26.24, "payment_days": 14, "lead_time_days": 35}}]`.
  - Après : `[{"terms": {"unit_price": 26.69, "payment_days": 90, "lead_time_days": 35}}, {"terms": {"unit_price": 26.69, "payment_days": 90, "lead_time_days": 28}}, {"terms": {"unit_price": 26.51, "payment_days": 60, "lead_time_days": 35}}]`.
- `arena-data/sessions/P05-0c33c2e26f104a11.json`, index 15, sup:70240, tour 3 : texte=True, feuilles=True, action=False.
  - Ajout : We have noted that those arguments are already reflected in your calculation; let us focus on the attached commercial terms.
  - Ajout : We have noted your limit on the current terms and are ready to complete our evaluation; any attached alternatives concern permitted commercial trades.
  - Ajout : This is the firm award volume for the attached package, rather than an additional uncommitted forecast.
  - Retrait : We are happy to pay faster if that helps your cash flow, in exchange for a better price.
  - Avant : `[{"terms": {"unit_price": 27.81, "payment_days": 90, "lead_time_days": 35}}, {"terms": {"unit_price": 27.81, "payment_days": 90, "lead_time_days": 28}}, {"terms": {"unit_price": 27.35, "payment_days": 14, "lead_time_days": 35}}]`.
  - Après : `[{"terms": {"unit_price": 27.81, "payment_days": 90, "lead_time_days": 35}}, {"terms": {"unit_price": 27.81, "payment_days": 90, "lead_time_days": 28}}, {"terms": {"unit_price": 27.63, "payment_days": 60, "lead_time_days": 35}}]`.
- `arena-data/sessions/P05-0c33c2e26f104a11.json`, index 21, sup:70240, tour 4 : texte=True, feuilles=False, action=False.
  - Ajout : We have noted that those arguments are already reflected in your calculation; let us focus on the attached commercial terms.
  - Ajout : We have noted your limit on the current terms and are ready to complete our evaluation; any attached alternatives concern permitted commercial trades.
  - Ajout : This is the firm award volume for the attached package, rather than an additional uncommitted forecast.

### P07 : exemples appariés

- `arena-data/sessions/P07-0b18b19250fe83d1.json`, index 1, sup:70610, tour 1 : texte=True, feuilles=True, action=False.
  - Retrait : We are happy to pay faster if that helps your cash flow, in exchange for a better price.
  - Avant : `[{"terms": {"unit_price": 4.59, "payment_days": 90, "contract_months": 24}}, {"terms": {"unit_price": 4.59, "payment_days": 90, "contract_months": 36}}, {"terms": {"unit_price": 4.51, "payment_days": 14, "contract_months": 24}}]`.
  - Après : `[{"terms": {"unit_price": 4.59, "payment_days": 90, "contract_months": 24}}, {"terms": {"unit_price": 4.59, "payment_days": 90, "contract_months": 36}}, {"terms": {"unit_price": 4.55, "payment_days": 60, "contract_months": 24}}]`.
- `arena-data/sessions/P07-0b18b19250fe83d1.json`, index 3, sup:70610, tour 2 : texte=True, feuilles=True, action=False.
  - Retrait : We are happy to pay faster if that helps your cash flow, in exchange for a better price.
  - Avant : `[{"terms": {"unit_price": 4.81, "payment_days": 90, "contract_months": 24}}, {"terms": {"unit_price": 4.81, "payment_days": 90, "contract_months": 36}}, {"terms": {"unit_price": 4.72, "payment_days": 14, "contract_months": 24}}]`.
  - Après : `[{"terms": {"unit_price": 4.81, "payment_days": 90, "contract_months": 24}}, {"terms": {"unit_price": 4.81, "payment_days": 90, "contract_months": 36}}, {"terms": {"unit_price": 4.77, "payment_days": 60, "contract_months": 24}}]`.
- `arena-data/sessions/P07-1915245dd410385e.json`, index 1, sup:70610, tour 1 : texte=True, feuilles=True, action=False.
  - Retrait : We are happy to pay faster if that helps your cash flow, in exchange for a better price.
  - Avant : `[{"terms": {"unit_price": 4.59, "payment_days": 90, "contract_months": 24}}, {"terms": {"unit_price": 4.59, "payment_days": 90, "contract_months": 36}}, {"terms": {"unit_price": 4.51, "payment_days": 14, "contract_months": 24}}]`.
  - Après : `[{"terms": {"unit_price": 4.59, "payment_days": 90, "contract_months": 24}}, {"terms": {"unit_price": 4.59, "payment_days": 90, "contract_months": 36}}, {"terms": {"unit_price": 4.55, "payment_days": 60, "contract_months": 24}}]`.

### P18 : exemples appariés

- `arena-data/sessions/P18-0fd3bcbc795c0d88.json`, index 1, sup:70740, tour 1 : texte=True, feuilles=True, action=False.
  - Retrait : We are happy to pay faster if that helps your cash flow, in exchange for a better price.
  - Avant : `[{"terms": {"unit_price": 4.88, "index_clause": null, "payment_days": 90, "contract_months": 24}}, {"terms": {"unit_price": 4.77, "index_clause": {"series": "AS-14404", "material_share": 0.45, "deadband_pct": 5, "base_month": "2026-08"}, "payment_days": 30, "contract_months": 24}}, {"terms": {"unit_price": 4.79, "index_clause": null, "payment_days": 14, "contract_months": 24}}]`.
  - Après : `[{"terms": {"unit_price": 4.88, "index_clause": null, "payment_days": 90, "contract_months": 24}}, {"terms": {"unit_price": 4.77, "index_clause": {"series": "AS-14404", "material_share": 0.45, "deadband_pct": 5, "base_month": "2026-08"}, "payment_days": 30, "contract_months": 24}}, {"terms": {"unit_price": 4.88, "index_clause": null, "payment_days": 90, "contract_months": 36}}]`.
- `arena-data/sessions/P18-0fd3bcbc795c0d88.json`, index 3, sup:70740, tour 2 : texte=True, feuilles=True, action=False.
  - Ajout : We have noted that those arguments are already reflected in your calculation; let us focus on the attached commercial terms.
  - Ajout : We have included your required index clause in each package; please improve the base price in return for that protection.
  - Ajout : We commit to a binding volume of 23,700 kg per year over 36 months.
  - Ajout : This is the firm award volume for the attached package, rather than an additional uncommitted forecast.
  - Retrait : We are happy to pay faster if that helps your cash flow, in exchange for a better price.
  - Retrait : We commit to a binding volume of 23,700 kg per year over 24 months.
  - Avant : `[{"terms": {"unit_price": 5.09, "index_clause": null, "payment_days": 90, "contract_months": 24}}, {"terms": {"unit_price": 4.98, "index_clause": {"series": "AS-14404", "material_share": 0.45, "deadband_pct": 5, "base_month": "2026-08"}, "payment_days": 30, "contract_months": 36}}, {"terms": {"unit_price": 5.0, "index_clause": null, "payment_days": 14, "contract_months": 24}}]`.
  - Après : `[{"terms": {"unit_price": 5.04, "index_clause": {"series": "AS-14404", "material_share": 0.45, "deadband_pct": 5, "base_month": "2026-08"}, "payment_days": 90, "contract_months": 36}}, {"terms": {"unit_price": 4.98, "index_clause": {"series": "AS-14404", "material_share": 0.45, "deadband_pct": 5, "base_month": "2026-08"}, "payment_days": 30, "contract_months": 36}}, {"terms": {"unit_price": 5.04, "index_clause": {"series": "AS-14404", "material_share": 0.45, "deadband_pct": 5, "base_month": "2026-08"}, "payment_days": 90, "contract_months": 24}}]`.
- `arena-data/sessions/P18-27b89ff53abe27fe.json`, index 1, sup:70740, tour 1 : texte=True, feuilles=True, action=False.
  - Retrait : We are happy to pay faster if that helps your cash flow, in exchange for a better price.
  - Avant : `[{"terms": {"unit_price": 4.88, "index_clause": null, "payment_days": 90, "contract_months": 24}}, {"terms": {"unit_price": 4.77, "index_clause": {"series": "AS-14404", "material_share": 0.45, "deadband_pct": 5, "base_month": "2026-08"}, "payment_days": 30, "contract_months": 24}}, {"terms": {"unit_price": 4.79, "index_clause": null, "payment_days": 14, "contract_months": 24}}]`.
  - Après : `[{"terms": {"unit_price": 4.88, "index_clause": null, "payment_days": 90, "contract_months": 24}}, {"terms": {"unit_price": 4.77, "index_clause": {"series": "AS-14404", "material_share": 0.45, "deadband_pct": 5, "base_month": "2026-08"}, "payment_days": 30, "contract_months": 24}}, {"terms": {"unit_price": 4.88, "index_clause": null, "payment_days": 90, "contract_months": 36}}]`.

### P08 : exemples appariés

- `arena-data/sessions/P08-2fc3680889612cdf.json`, index 1, sup:70710, tour 1 : texte=True, feuilles=True, action=False.
  - Retrait : We are happy to pay faster if that helps your cash flow, in exchange for a better price.
  - Avant : `[{"terms": {"unit_price": 4.84, "index_clause": null, "payment_days": 90, "contract_months": 24}}, {"terms": {"unit_price": 4.73, "index_clause": {"series": "AS-14404", "material_share": 0.45, "deadband_pct": 5, "base_month": "2026-08"}, "payment_days": 30, "contract_months": 24}}, {"terms": {"unit_price": 4.75, "index_clause": null, "payment_days": 14, "contract_months": 24}}]`.
  - Après : `[{"terms": {"unit_price": 4.84, "index_clause": null, "payment_days": 90, "contract_months": 24}}, {"terms": {"unit_price": 4.73, "index_clause": {"series": "AS-14404", "material_share": 0.45, "deadband_pct": 5, "base_month": "2026-08"}, "payment_days": 30, "contract_months": 24}}, {"terms": {"unit_price": 4.84, "index_clause": null, "payment_days": 90, "contract_months": 36}}]`.
- `arena-data/sessions/P08-2fc3680889612cdf.json`, index 3, sup:70710, tour 2 : texte=True, feuilles=False, action=False.
  - Ajout : We have noted that those arguments are already reflected in your calculation; let us focus on the attached commercial terms.
  - Ajout : We have included your required index clause in each package; please improve the base price in return for that protection.
- `arena-data/sessions/P08-2fc3680889612cdf.json`, index 5, sup:70710, tour 3 : texte=True, feuilles=False, action=False.
  - Ajout : We have noted that those arguments are already reflected in your calculation; let us focus on the attached commercial terms.
  - Ajout : We have included your required index clause in each package; please improve the base price in return for that protection.

### P02 : exemples appariés

- `arena-data/sessions/P02-20fdbb9beda2862b.json`, index 1, sup:70510, tour 1 : texte=True, feuilles=True, action=False.
  - Retrait : We are happy to pay faster if that helps your cash flow, in exchange for a better price.
  - Avant : `[{"terms": {"unit_price": 362.11, "payment_days": 90, "index_clause": null}}, {"terms": {"unit_price": 355.93, "payment_days": 14, "index_clause": {"series": "CU-NOTATION", "material_share": 0.2, "deadband_pct": 5, "base_month": "2026-08"}}}, {"terms": {"unit_price": 356.01, "payment_days": 14, "index_clause": null}}]`.
  - Après : `[{"terms": {"unit_price": 362.11, "payment_days": 90, "index_clause": null}}, {"terms": {"unit_price": 355.93, "payment_days": 14, "index_clause": {"series": "CU-NOTATION", "material_share": 0.2, "deadband_pct": 5, "base_month": "2026-08"}}}]`.
- `arena-data/sessions/P02-20fdbb9beda2862b.json`, index 3, sup:70510, tour 2 : texte=True, feuilles=True, action=False.
  - Ajout : We have noted that those arguments are already reflected in your calculation; let us focus on the attached commercial terms.
  - Ajout : This is the firm award volume for the attached package, rather than an additional uncommitted forecast.
  - Retrait : We are happy to pay faster if that helps your cash flow, in exchange for a better price.
  - Avant : `[{"terms": {"unit_price": 362.11, "payment_days": 90, "index_clause": null}}, {"terms": {"unit_price": 355.93, "payment_days": 14, "index_clause": {"series": "CU-NOTATION", "material_share": 0.2, "deadband_pct": 5, "base_month": "2026-08"}}}, {"terms": {"unit_price": 356.01, "payment_days": 14, "index_clause": null}}]`.
  - Après : `[{"terms": {"unit_price": 362.11, "payment_days": 90, "index_clause": null}}, {"terms": {"unit_price": 355.93, "payment_days": 14, "index_clause": {"series": "CU-NOTATION", "material_share": 0.2, "deadband_pct": 5, "base_month": "2026-08"}}}]`.
- `arena-data/sessions/P02-20fdbb9beda2862b.json`, index 5, sup:70510, tour 3 : texte=True, feuilles=True, action=False.
  - Ajout : We have noted that those arguments are already reflected in your calculation; let us focus on the attached commercial terms.
  - Ajout : This is the firm award volume for the attached package, rather than an additional uncommitted forecast.
  - Retrait : We are happy to pay faster if that helps your cash flow, in exchange for a better price.
  - Avant : `[{"terms": {"unit_price": 362.11, "payment_days": 90, "index_clause": null}}, {"terms": {"unit_price": 355.93, "payment_days": 14, "index_clause": {"series": "CU-NOTATION", "material_share": 0.2, "deadband_pct": 5, "base_month": "2026-08"}}}, {"terms": {"unit_price": 356.01, "payment_days": 14, "index_clause": null}}]`.
  - Après : `[{"terms": {"unit_price": 362.11, "payment_days": 90, "index_clause": null}}, {"terms": {"unit_price": 355.93, "payment_days": 14, "index_clause": {"series": "CU-NOTATION", "material_share": 0.2, "deadband_pct": 5, "base_month": "2026-08"}}}]`.

## Validation et portée

**23 tests réussis**. **203 archives / 1076 décisions par version** ; exceptions=0, violations techniques=0, promesses fixes impossibles=0, nouvelles régressions=0. **203 clôtures au cap** contrôlées ; changements=0.

Le replay vérifie champs/options/must-haves, prix sous l’ask, IDs d’acceptation et coûts au budget ou au plancher relationship déjà présent dans r10. Toute action historique différente reste recensée ; aucune réponse nouvelle, ni nouveau score, n’est inventée. Standards contextuels de replay : les PDF sont absents des exports.

[ROUND10_REPLAY.json](../intel/generated/ROUND10_REPLAY.json) conserve les décisions appariées ; [ROUND10_VALIDATION.json](../intel/generated/ROUND10_VALIDATION.json) fournit empreintes, compilation et application exacte du [patch](latest-r10-proposed/FROM_R10.patch). Seuls agent.py et reader.py changent dans les treize modules proposés ; les onze autres sont identiques.

La règle d’index exige désormais la famille dans toutes les offres après un signal obligatoire ; elle peut renoncer à un contrat court sans clause qui aurait été recevable si l’exigence était conditionnelle à la durée. Les durées plus longues et délais fermes peuvent aussi durcir notre menu : essais mesurés nécessaires. Le gel conserve les trades, pas une marge fournisseur privée. Les gains de score ne sont pas prouvés par cette revue.

Le remplacement du vieux CASH_RE retire le signal de cash automatiquement déduit du seul mot Zahlungsziel. Certaines alternatives 14 j deviennent donc des alternatives 60 j avant une demande explicite de paiement rapide : changement réel dans P05/P07 et les demos, sans preuve qu’il améliore le score. D01/D02 changent aussi ; leurs anciens scores ne valident pas cette nouvelle politique.

Aucun appel réseau ni nouvelle session ; latest-r10 et les traces restent intacts. Proposition prête pour comparer les seuls cas dont les messages changent.
