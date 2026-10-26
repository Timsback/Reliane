# Reliane 1.1 — gestionnaire d'équipe Dofus

Compagnon Windows pour organiser et parcourir vos fenêtres **Dofus Unity et Rétro**. L'interface sombre reprend les panneaux ardoise et les onglets d'inventaire du jeu. L'emblème est l'icône du Dofus Émeraude ; les portraits proviennent de votre installation locale. Aucun décor ou logo généré par IA n'est utilisé dans l'application.

## Essayer

Double-cliquez sur **`Reliane.exe` à la racine**, ou sur **`Lancer Reliane.bat`**. `dist\Reliane.exe` est une seconde copie du même lanceur. Le lanceur ouvre la dernière version installée et vérifie son empreinte SHA-256. Python n'est pas nécessaire pour lancer une version déjà construite.

Pour découvrir l'interface sans lancer Dofus : **`Essayer la demo.bat`**. Les personnages de cette démonstration sont fictifs, aucun raccourci global n'est installé et aucune configuration réelle n'est modifiée.

1. Ouvrez les clients Dofus et connectez vos personnages.
2. Choisissez **Unity** ou **Rétro** au-dessus de la liste. La détection se renouvelle toutes les 1,5 seconde.
3. Incluez les personnages dans le cycle avec leur case. Choisissez le meneur avec l'étoile.
4. Réglez l'initiative avec les flèches, ou cliquez sur le numéro pour choisir une position précise.
5. Le petit bouton **1 / 2** change l'équipe ; **···** donne accès aux détails et à une demande de fermeture normale du jeu.
6. Réglez vos touches dans **Raccourcis** et mémorisez votre organisation avec une **composition**.

La croix masque Reliane dans la zone de notification. Quittez avec le menu de cette icône ou dans **Réglages → Quitter Reliane**. Avec `--no-tray`, la croix quitte directement.

## Raccourcis par défaut

Les touches présentes dans votre ancien fichier sont conservées ; ce tableau décrit une nouvelle configuration.

| Action | Touche |
|---|---|
| Suivant | ² |
| Précédent | Tab |
| Meneur | F1 |
| Afficher / masquer | F10 |
| Mettre en pause / reprendre | Ctrl + F10 |
| Actualiser | F5 |
| Accès aux places 1 à 8 | Ctrl + F1 à Ctrl + F8 |
| Quitter | Non défini |

Une pression produit une action, sans répétition tant que la touche reste tenue. Les touches sont transmises au jeu : choisissez des combinaisons qui ne gênent pas vos commandes Dofus.

Par défaut, la navigation s'applique uniquement lorsque Dofus est au premier plan. L'affichage et la pause restent accessibles partout. Reliane ignore la navigation pendant la saisie dans ses propres fenêtres. Les touches **Ctrl + 1, 2, 3** ouvrent ses trois espaces ; les boutons acceptent Tab, Entrée et Espace.

Pour changer une touche, cliquez dessus, appuyez sur la combinaison puis relâchez. Échap annule ; la capture expire après dix secondes. Les conflits, y compris deux noms pour une même touche physique, sont signalés. La disposition AZERTY/QWERTY concerne Reliane et ne change pas le clavier Windows.

## Compositions et sauvegardes

Une composition mémorise l'ordre, les équipes, les inclusions dans le cycle, le meneur, les classes, la version de jeu et les accès directs. **Nouvelle** crée un instantané ; **Enregistrer** met à jour la composition choisie. Les changements de session restent enregistrés dans les réglages même sans actualiser cet instantané. Charger une autre composition demande confirmation si des ajustements n'ont pas été enregistrés.

Les réglages restent dans **`dist\settings.json`**, indépendamment des versions successives. Le lanceur transmet ce chemin à l'application. Le fichier historique présent dans `dist` est réutilisé ; l'ancien `MyDosoft.exe` est conservé. Depuis les sources, le premier lancement peut copier la configuration de `dist`, puis celle de l'installation Dosoft si nécessaire. Pour partager exactement les réglages de l'exécutable depuis les sources, utilisez `--config dist\settings.json`.

## Mises à jour

Le lanceur stable lit `dist\release.json` et ouvre la version vérifiée indiquée dans `dist\releases\`. Une nouvelle version ne remplace jamais un binaire en cours d'exécution. Si Reliane est déjà ouvert, une nouvelle demande de lancement affiche sa fenêtre ; si la version a changé, Reliane propose un redémarrage.

Dans ce dossier de développement, le lanceur compare aussi le code et les ressources avec la version construite. Si le projet a changé, il propose de reconstruire automatiquement l'application avec l'environnement `.venv`. L'ancienne version et les réglages sont conservés si la construction échoue. `Reliane.exe --update` demande cette reconstruction directement.

Pour la copie Git reliée à **`https://github.com/Timsback/Reliane.git`**, le lanceur vérifie également les nouveaux commits de `main`. Une mise à jour GitHub est proposée avant tout téléchargement dans la copie de travail. Elle n'est appliquée que si la branche est `main`, que les fichiers suivis sont propres et qu'une fusion en avance rapide est possible. Les modifications locales ne sont pas écrasées. La mise à jour installe les dépendances verrouillées puis reconstruit la version locale. Git et l'environnement Python du projet doivent être disponibles pour ce mécanisme.

Hors ligne, ou sans copie Git du projet, la dernière version locale reste utilisable. **Réglages → Vérifier les mises à jour** relance cette vérification. Les nouveautés ne peuvent apparaître que lorsqu'une nouvelle version du code a effectivement été publiée ; le logiciel ne génère pas lui-même des mises à jour.

Chaque enregistrement remplace le JSON de façon atomique et conserve la version précédente dans `.bak`. Un fichier illisible reste protégé : Reliane essaie sa sauvegarde, signale le problème et suspend les écritures jusqu'à un import explicite. **Réglages → Importer / Exporter** permet de conserver ou de transférer une sauvegarde. Un import conserve aussi une copie datée du fichier précédent. Les clés héritées inconnues restent préservées.

## Roue, notifications et barre Windows

- **Roue** : activez-la dans Réglages. Maintenez une combinaison souris, survolez un portrait et relâchez. Revenir au centre annule. Alt + clic gauche est proposé ; un bouton latéral est souvent plus confortable.
- **Notifications Rétro** : option facultative, inactive pour Unity. Windows doit autoriser leur lecture. Seules les nouvelles notifications identifiées comme Dofus ou Ankama sont examinées ; elles ne sont jamais supprimées. La pause suspend aussi cet auto-focus. Le refus d'accès n'empêche pas les autres fonctions de marcher.
- **Barre des tâches** : les fenêtres du cycle sont masquées puis restaurées dans l'ordre. Le regroupement de Windows peut empêcher un classement visuel exact. Les fenêtres déjà masquées par l'opération sont restaurées même si une autre disparaît pendant le rangement.
- **Fermeture de jeu** : Reliane envoie `WM_CLOSE`, après votre confirmation. Il ne termine pas les processus de force ; le jeu peut demander sa propre confirmation.

## Installation et développement

Windows 10/11, Python **3.12 64 bits** pour les sources. Le binaire livré a été construit sur Windows 11.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-lock.txt
.\.venv\Scripts\python fetch_assets.py
.\.venv\Scripts\python main.py --config dist\settings.json
```

```powershell
# Démonstration isolée
.\.venv\Scripts\python main.py --demo --no-tray
# Vérifications
.\.venv\Scripts\python -m unittest discover -s tests -v
# Compilation reproductible
.\build.bat
```

`build.bat` installe les versions verrouillées, récupère les ressources, exécute les tests et construit une version immuable et les deux copies du lanceur. Il n'efface pas les réglages. `build_release.py --app-only` construit uniquement la nouvelle application et actualise le manifeste. Pour vérifier le packaging sans ouvrir de fenêtre : `Reliane.exe --self-test qa-output\packaging.json`.

Le dépôt public ne contient pas les ressources graphiques Dofus. `fetch_assets.py` récupère l'icône Émeraude depuis le CDN d'Ankama, avec DofusDB comme miroir de repli, et cherche les portraits dans `C:\Program Files (x86)\Dosoft\skin`. Les images reçues sont validées puis normalisées en PNG. Passez `--skin CHEMIN` pour choisir un autre dossier. Sans portraits locaux, des symboles de secours s'affichent. Les ressources de jeu restent soumises aux droits de leurs titulaires ; voir `assets/NOTICE.md`.

L'application démarre sans élévation. Si vos clients Dofus sont eux-mêmes administrateurs et que Windows empêche les raccourcis ou le focus, lancez explicitement `dist\Reliane.exe --admin`. `--no-admin` reste accepté pour compatibilité. N'utilisez pas simultanément plusieurs gestionnaires avec les mêmes raccourcis.

## Vérifications et limites

Voir **`VERIFICATION.md`** pour le détail des tests et des essais d'interface. L'interface est adaptative de 620 px à un grand écran ; c'est une application Windows, sans version mobile. Le comportement dans une véritable session Dofus et les autorisations Windows de notifications restent à confirmer en jeu. Le binaire n'est pas signé avec un certificat commercial.

Les données de jeu restent locales. Reliane ne demande aucun identifiant de jeu, n'enregistre pas les frappes saisies et n'injecte aucun code dans le jeu. Seul le lanceur utilise le réseau pour vérifier et récupérer les mises à jour du dépôt public. Les erreurs techniques vont dans `reliane.log`, à côté des réglages, avec rotation limitée ; les constructions automatiques sont consignées dans `update-build.log`.

Les portraits repris de l'installation locale sont documentés dans **`assets/NOTICE.md`**. La disponibilité commerciale du nom et d'un domaine n'est pas garantie : voir **`DIRECTION_ARTISTIQUE.md`**.

## Repères dans le code

`main.py` : cycle de vie et navigation · `launcher.py` : lancement et mises à jour · `build_release.py` / `release_tools.py` : versions et intégrité · `windows.py` : fenêtres Win32 · `hotkeys.py` : touches et validation · `config.py` : stockage et compositions · `gui.py` : interface et tray · `smooth_widgets.py` : contours supersamplés · `radial.py` : roue · `notifications.py` : écoute facultative · `icons.py` : portraits · `theme.py` : identité · `demo.py` : données fictives isolées.
