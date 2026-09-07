# SPEC — LA TAUPE

## Problème (5 lignes)
Un utilisateur fournit une question et un corpus de documents hétérogènes.
Certains documents contiennent des instructions cachées destinées à manipuler l'agent (injection de prompt indirecte).
L'agent doit produire une réponse correcte en n'utilisant que les documents légitimes.
Il doit détecter et mettre en quarantaine les documents piégés.
Il doit produire un rapport d'audit traçant chaque tentative détectée avec l'extrait déclencheur.

## User Stories
1. **En tant qu'analyste**, je dépose un corpus mixte (documents sains + au moins un piégé) et je reçois une réponse fondée uniquement sur les documents sains, avec un rapport listant chaque document suspect, l'extrait incriminé et la technique détectée.
2. **En tant qu'analyste**, je consulte le panneau d'audit pour voir l'historique complet des détections : document, extrait, technique, confiance, horodatage, décision (quarantaine/accepté).
3. **En tant qu'analyste**, je soumets une question en langage naturel et j'obtiens une réponse citant ses sources (documents sains uniquement), sans que le contenu des documents en quarantaine n'ait influencé la génération.

## Hors Scope (6 items)
- Nettoyage partiel du document : Un document piégé est écarté à 100 % ; nous ne tentons pas d'en extraire les morceaux "sains".
- Traitement des images et fichiers exécutables (OCR / Stéganographie) : Analyse limitée aux fichiers texte brut et structurés (PDF, TXT, MD, JSON).
- Gestion des rôles et authentification (RBAC / Multitenant) : Pas de système de comptes utilisateurs ni de gestion de permissions complexes.
- Entraînement ou fine-tuning de modèle local : Utilisation d'API LLM existantes combinées à des garde-fous algorithmiques et contextuels.
- Prévention des injections directes dans l'UI : Le périmètre de sécurité se focalise sur l'injection indirecte présente au sein du corpus de fichiers.
- Correction automatique du code par l'agent : L'agent signale et isole la menace, mais ne modifie pas sa propre logique ou ses garde-fous à chaud.

## Happy Path — Démo finale (6 étapes)
1. **Upload** : L'analyste glisse-dépose un corpus ZIP/JSON (ex: 5 PDF + 1 TXT piégé) + sa question (« Quels sont les risques chimiques mentionnés ? »).
2. **Ingestion & criblage** : Le backend parse, normalise, attribue un `doc_id` à chaque document, puis le module de détection analyse chaque document indépendamment → 1 document mis en quarantaine (technique `override_direct`, extrait visible), 5 documents marqués `clean`.
3. **Recherche sur corpus sain** : L'agent invoque `search_corpus(question, k=5, corpus_id)` → récupère les passages pertinents **uniquement** depuis les 5 documents `clean`.
4. **Génération réponse citée** : L'agent produit la réponse en s'appuyant exclusivement sur les hits retournés, puis appelle `cite_sources` pour attacher les citations précises (doc_id, chunk_id, span).
5. **Rapport d'audit** : L'agent appelle `list_quarantine(corpus_id)` → récupère la liste structurée des détections, puis `finalize_report` pour persister le tout (réponse + citations + quarantaine + horodatage).
6. **Affichage dashboard** : Le frontend reçoit le `Report` complet → affiche la réponse avec citations cliquables, le panneau quarantaine (document suspect, technique, extrait, confiance), et le statut « Corpus traité ».

## Répartition du travail (Trinôme — écrit noir sur blanc)

| Membre | Rôle | Responsabilités principales (paliers 1→4) |
|--------|------|-------------------------------------------|
| **Yo** | Moteur Agentique & Sécurité | Boucle de décision LLM, définition/typage strict des outils (OUTILS.md), barrières détection injection (classifieur / LLM-juge / règles), étanchéité données/instructions (prompts système, séparation contextes), tests adversariaux, faux positifs. |
| **Kévin** | Backend & Pipeline | Structure projet, `.gitignore`, `.env.example`, parsing/ingestion documents (PDF, TXT, DOCX), normalisation Unicode, découpage chunks, registre BDD quarantaine (`quarantine_entries`, `reports`), logs sécurité structurés, API routes (`/ingest`, `/query`, `/report`), déploiement. |
| **Niko** | Interface Front-End | Dashboard upload (drag-drop, progression temps réel via SSE/WS), affichage réponse finale avec citations cliquables, panneau audit quarantaine (tableau + détail extrait), indicateurs de confiance, gestion d'erreurs, accessibilité. |

**Points de synchronisation obligatoires** :
- Contrat API (`/ingest` → `corpus_id`, `/query` → `Report`) figé avant Palier 2.
- Schéma BDD (documents, chunks, quarantine_entries, reports) validé par Kévin + Yo avant migration.
- Format des extraits de quarantaine (longueur, échappement) convenu Yo ↔ Niko pour l'affichage audit.