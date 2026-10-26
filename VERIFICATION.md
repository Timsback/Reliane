# Vérification de Reliane 1.1

Validation locale sous Windows 11, Python 3.12 64 bits, le 26 octobre 2026.

## Tests automatisés

La suite contient 32 tests et vérifie notamment :

- la conservation des réglages hérités et des clés inconnues ;
- les écritures atomiques, les sauvegardes, les fichiers endommagés et les erreurs de disque ;
- l'indépendance des compositions, leur rechargement et leur persistance ;
- les titres Unity/Rétro, l'ordre filtré, les états, le meneur et la fermeture normale ;
- les conflits de touches physiques, les modificateurs et l'absence de répétition à touche maintenue ;
- les parcours sur les vrais widgets Tk aux formats 1080 × 880 et 620 × 660 ;
- les états distincts des interrupteurs, les contours antialiasés et les contrastes des textes ;
- la présence des 31 portraits sur cette installation et la transparence du logo ;
- le refus d'une version modifiée ou d'un chemin sortant du dossier des versions ;
- la détection des changements du projet sans boucle de reconstruction sur les métadonnées ;
- les mises à jour Git avec accord, le refus d'une mise à jour et la préservation des réglages et des modifications locales ;
- l'indépendance entre le dossier des versions et un chemin de réglages personnalisé ;
- la confirmation de redémarrage et le réamorçage indépendant de l'exécutable compilé.

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -v
```

Le test Git utilise un dépôt nu et deux copies temporaires isolées. Aucune mise à jour fictive n'est publiée sur le dépôt réel pour ce test.

## Vérification Win32 et binaire

Une fenêtre Win32 Unity créée par les tests est détectée avec `EnumWindows` puis fermée par `WM_CLOSE`. Ce test ne manipule aucun vrai client Dofus.

Le binaire construit est vérifié avec `Reliane.exe --self-test CHEMIN_JSON` : version embarquée, identifiant de construction, ressources requises, portraits et import des projections WinRT. Le lanceur vérifie aussi l'empreinte SHA-256 du fichier avant exécution.

Les versions sont construites dans des dossiers séparés, avec un marqueur de fin de construction. Le manifeste courant n'est changé qu'après la réussite de la construction. L'ancien exécutable MyDosoft et les réglages existants sont conservés.

Les processus qui doivent survivre au lanceur ou à l'ancienne instance sont amorcés avec `PYINSTALLER_RESET_ENVIRONMENT=1`. Le lanceur rétablit le chemin de recherche des DLL système avant d'appeler Git ou Python, conformément aux [instructions PyInstaller](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html).

## Contrôles d'interface

Les écrans Équipe, Raccourcis et Réglages ont été ouverts dans l'exécutable Windows. Le passage au personnage suivant et l'annulation de capture par Échap ont été essayés sur l'équipe de démonstration. Les captures de travail sont conservées localement dans `previews/`, hors dépôt public.

La démonstration contient des personnages fictifs clairement signalés et ne modifie pas les réglages réels. Les essais d'instance unique et de redémarrage utilisent un chemin de réglages de test séparé.

La confirmation intégrée a été affichée puis validée dans le binaire. La nouvelle instance est revenue avec un nouvel identifiant de fenêtre et ses propres ressources temporaires, sans erreur après le transfert. La demande de mise à jour était simulée dans le dossier de test ; aucune fausse version n'a été publiée.

## Limites restantes

- Aucun véritable combat Dofus n'a été utilisé pendant cette validation. Le focus et les raccourcis face à un client lancé en administrateur restent à confirmer en jeu.
- L'import du module de notifications est vérifié ; l'autorisation Windows et la réception d'une véritable notification Rétro ne le sont pas.
- Le classement visuel de la barre des tâches dépend du regroupement de Windows.
- La mise à jour du dépôt est testée sur un dépôt isolé ; une future publication réelle ne peut être vérifiée avant qu'elle existe.
- L'exécutable n'est pas signé avec un certificat commercial.
- Il s'agit d'une application Windows adaptative, sans version mobile.
