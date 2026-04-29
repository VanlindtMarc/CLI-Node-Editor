![Logo](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/Terminal%20Architect%20Logo%20final.svg)

# 🏗️ Terminal Architect

> 🧰 **Terminal Architect** est une application de bureau qui permet de **construire des scripts CLI complexes** (Batch `.bat`, Bash `.sh`, PowerShell `.ps1`) à travers une **interface nodale visuelle**, sans écrire une seule ligne de script à la main.

L'idée : assembler graphiquement des nœuds — un par commande, un par décision, un par variable — puis laisser l'application générer le script correspondant. Le script obtenu peut ensuite être appelé directement depuis l'**Explorateur Windows** (clic droit ➜ **Envoyer vers…**), ce qui transforme n'importe quel flux ffmpeg / ImageMagick / yt-dlp / HandBrake / etc. en **outil contextuel** sur vos fichiers.

🪟 Le **Batch** reste le langage de prédilection sous Windows : c'est le seul format directement exécutable depuis l'Explorateur sans bricolage de la sécurité système, contrairement à PowerShell (`.ps1`) qui nécessite un déblocage manuel.

---

## 📚 Sommaire

1. [✨ Fonctionnalités](#-fonctionnalités-principales)
2. [⚡ Démarrage rapide](#-démarrage-rapide)
3. [🖥️ Interface](#-interface)
4. [🔧 Outils CLI](#-outils-cli)
5. [🧩 Nœuds](#-nœuds)
6. [🔁 Modes de flux](#-modes-de-flux)
7. [🐞 Débogage](#-débogage)
8. [📦 Bibliothèque](#-bibliothèque)
9. [▶️ Exécution & export](#-exécution--export)
10. [💡 Exemples de nœuds](#-exemples-de-nœuds)
11. [🌊 Exemples de flux](#-exemples-de-flux)
12. [🛠️ Compilation avec PyInstaller](#-compilation-avec-pyinstaller)
13. [📂 Fichiers de configuration](#-fichiers-de-configuration)
14. [🪲 Bugs connus](#-bugs-connus)
15. [🚀 Roadmap](#-roadmap)
16. [📜 Liste des CLI compatibles](#-liste-des-cli-compatibles)

---

## ✨ Fonctionnalités principales

- 🎨 **Éditeur nodal** drag & drop avec connexions Bézier, mini-map, recadrage automatique (`Ctrl+0`) et recherche de nœud (`Ctrl+F`).
- 🌐 **Trois langages cibles** : Batch, Bash, PowerShell — choisis dans la colonne de gauche, le code se régénère à la volée.
- 🧠 **Bibliothèque de nœuds** importable / exportable (`node_library.json`) — chaque nœud encapsule une commande CLI réutilisable.
- 🔌 **Gestionnaire de dépendances** centralisé (`dependencies.json`) : on déclare ses outils CLI une fois, on les invoque partout par leur nom court.
- 👁️ **Prévisualisation live** du script avec coloration syntaxique adaptée à chaque langage.
- ▶️ **Exécution intégrée** avec retour visuel (le nœud en cours s'illumine) et console de log dans l'interface.
- 🐛 **Mode debug** : injection de traces et de pauses pas-à-pas dans le script généré.
- 💾 **Workflows** sauvegardables au format `.workflow` + menu **Flux récents** (16 derniers).
- 🪵 **Trois modes d'entrée** : un fichier à la fois, plusieurs en lot, ou liste depuis un fichier texte.
- 🎯 **Switch / Merge / Math SI** pour les flux conditionnels (orientation d'image, format audio, etc.).

---

## ⚡ Démarrage rapide

### 🐍 Depuis les sources

```bash
pip install PyQt6
python "Terminal Architect.py"
```

### 📥 Depuis l'exécutable compilé

1. Téléchargez `Terminal Architect.exe`.
2. Placez-le dans un dossier dédié — il créera ses fichiers de config à côté de lui au premier lancement (`dependencies.json`, `node_library.json`, `recent_workflows.json`).
3. Configurez vos outils CLI via **Outils ➜ Configurer les dépendances** avant la première utilisation.

### 🪄 Astuce « Envoyer vers »

Pour que vos workflows apparaissent dans le menu contextuel Windows :

1. Exportez le workflow en `.bat` (**Fichier ➜ Exporter le script**).
2. Tapez `shell:sendto` dans la barre d'adresse de l'Explorateur.
3. Glissez-y un raccourci vers votre `.bat`.

---

## 🖥️ Interface

L'interface se divise en **trois colonnes** :

### 1. 📚 Colonne gauche — Bibliothèque & options globales

- 🔍 Filtre **Tous les nœuds** / **Nœuds vérifiés** (les nœuds vérifiés ont été testés ; les autres sont souvent générés par IA et n'attendent que votre validation).
- ☑️ **Boucler sur chaque fichier** : applique le flux à chaque fichier indépendamment, ou en un seul passage groupé.
- 📜 **Type de script** : Batch, Bash ou PowerShell.
- 🐞 **Mode debug** + **Pause avant chaque action**.
- ➕ **Nouveau** : crée un nœud personnalisé.
- ✏️ **Éditer** / 📋 **Utiliser comme template** / 🗑️ **Supprimer** : actions sur le nœud sélectionné.
- 👉 Double-clic sur un nœud de la liste = ajout immédiat sur le canvas.

### 2. 🎨 Zone centrale — Canvas

- 🖱️ Clic droit sur le fond ➜ menu hiérarchisé pour insérer un nœud à la position du curseur.
- 🔗 Tirez un câble depuis un port pour créer une connexion.
- 🎯 `F` pour centrer la vue sur le nœud sélectionné, `Ctrl+0` pour cadrer tout le workflow.
- 🔢 Chaque nœud affiche son **numéro d'ordre d'exécution**, recalculé en temps réel.

### 3. 📜 Colonne droite — Aperçu & exécution

- 🧾 **Aperçu du script** avec coloration syntaxique (Batch / Bash / PowerShell).
- 🔄 **Recalculer l'ordre** force la régénération.
- ▶️ **Lancer** : exécute le workflow depuis l'interface (les fichiers d'entrée sont demandés via boîte de dialogue).
- ⏹️ **Stop** pour interrompre.
- 📟 **Console d'exécution** : sortie standard fusionnée du process en cours, avec nœuds animés en temps réel.

![Interface](https://github.com/VanlindtMarc/be/blob/main/README/CLI02.png)

---

## 🔧 Outils CLI

![CLI11](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI11.png)

Avant la première utilisation : déclarez les outils CLI installés sur votre machine dans **Outils ➜ Configurer les dépendances**. Pour chacun :

| Champ | Description |
|---|---|
| 🏷️ **Nom court** | L'identifiant utilisé dans vos templates (ex. `ffmpeg`). C'est ce nom qui fait le pont entre nœud et exécutable. |
| 📁 **Chemin** | Chemin complet vers le binaire — vous évite d'avoir à polluer votre `%PATH%`. Si rempli, c'est ce chemin qui sera injecté dans le script. |
| 📝 **Description** | Mémo libre. |
| ❓ **Arg version** | L'argument à passer pour récupérer la version (`--version`, `-version`, `-ver`…). Sert au bouton de test. |

> ⚠️ **Important** : ne renommez pas un outil après coup. Tous les nœuds qui pointent vers ce nom court cesseront de fonctionner.

La configuration vit dans `dependencies.json` (voir [📂 Fichiers de configuration](#-fichiers-de-configuration)).

---

## 🧩 Nœuds

Un **nœud** = une étape du flux. Quatre familles existent :

### 📥 Nœuds Fichier (entrées / sortie)

Ces nœuds sont **gérés en interne** par Terminal Architect — non éditables.

- 📄 **Fichier Input** *(par défaut)* : le ou les fichiers passés au script à son lancement (`%~1`, `$1`, `$args[0]`).
- 📌 **Fichier Source** : un fichier fixe (ex. un watermark PNG toujours appliqué).
- 🗂️ **Multi-fichiers** : déclare un nombre de fichiers attendus, chacun filtré par extension.
- 📋 **Liste** : prend un fichier texte en entrée et boucle sur chacune de ses lignes (utile pour des listes d'URL avec yt-dlp).
- 🎯 **Fichier Destination** *(sortie)* : nom du résultat final. Peut être instancié plusieurs fois si le flux produit plusieurs livrables.

### ⚙️ Nœuds Système

- ❓ **Variables d'entrée** : pose une série de questions à l'utilisateur au démarrage du script — chaque réponse devient une variable.
- 🌐 **Variables Globales** : transforme une entrée du flux (résultat d'une commande, ex. `ffprobe`) en variable globale réutilisable.
- 🔀 **Switch** : aiguille le flux selon une condition (ex. format du fichier, dimensions de l'image).
- 🔗 **Merge** : réunit les branches après un Switch pour repartir sur un tronc commun.
- ➗ **Math SI** / **Math SI if elseif** : tests booléens et conditions multi-cas.
- 🐛 **Debug** : affiche le contenu d'une variable ou d'un fichier au milieu du flux.

### 🛠️ Nœuds créés (custom)

C'est là que la richesse de l'application se trouve. Chaque nœud personnalisé décrit **une commande CLI** dans son template, avec ports et paramètres. Quatre onglets dans la fenêtre de création :

#### 1. 📋 Général

![CLI12](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI12.png)

- 🏷️ **Nom du nœud** *(unique)*
- 👁️ **Nom affiché** dans les menus
- 📂 **Catégorie** *(souvent le nom de la CLI)*
- 📁 **Sous-catégorie** *(type d'usage)*
- 💻 **Commande CLI** : **nom court** déclaré dans Outils → c'est ce qui résout le chemin réel à la génération.
- 🎬 **Format de sortie** par défaut + 📐 **Formats suggérés**
- 📝 **Description**
- 🎨 **Couleur hexa** affichée sur le nœud

> ⚠️ La **commande CLI** doit correspondre **exactement** à un nom court du gestionnaire d'outils, sinon le script ne saura pas où trouver l'exécutable.

#### 2. 🔌 Ports

![CLI13](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI13.png)

Définit le nombre de ports d'entrée et de sortie. Dans le template, on les référence par `{input}`, `{input2}`, … et `{output}`, `{output2}`, …

#### 3. 🎚️ Paramètres

![CLI14](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI14.png)

Variables locales du nœud (largeur, qualité, encodeur…) avec valeurs par défaut, types et choix prédéfinis. Elles deviennent éditables directement sur le nœud une fois posé sur le canvas.

#### 4. 🧱 Template

![CLI15](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI15.png)

La ligne de commande, paramétrée par les variables locales (`{width}`) et globales (`{Encodeur}`), avec `{input}` / `{output}` pour les ports.

---

## 🔁 Modes de flux

Trois logiques d'entrée sont possibles selon les nœuds d'entrée placés :

| Mode | Nœud à utiliser | Comportement |
|---|---|---|
| 🔂 **Un fichier à la fois** | `Fichier Input` + ☑️ *Boucler sur chaque fichier* | Le workflow s'exécute une fois par fichier passé en argument. |
| 🧺 **Lot global** | `Fichier Input` + ☐ *Boucler sur chaque fichier* | Tous les fichiers sont disponibles ensemble dans un même run. |
| 📋 **Liste** | `Liste` | Lit un fichier texte ligne par ligne et applique le flux à chaque ligne. |
| 🗂️ **Multi-fichiers typés** | `Multi-fichiers` | Demande N fichiers, chacun avec une extension précise. |

---

## 🐞 Débogage

- 🐛 **Mode debug** : insère dans le script généré des `echo` détaillés indiquant chaque étape, chaque variable résolue, le statut de retour de chaque commande.
- ⏸️ **Pause avant chaque action** *(actif uniquement si Debug activé)* : ajoute un `pause` avant chaque nœud pour avancer manuellement dans le flux et inspecter l'état.
- 🔍 **Nœud Debug** : sonde le contenu d'une variable ou d'un fichier au milieu du flux.
- 📡 **Console d'exécution intégrée** : pendant un `Lancer`, les marqueurs `__NODE_START__` / `__NODE_END__` permettent à l'interface d'illuminer le nœud en cours en temps réel.

---

## 📦 Bibliothèque

- 📥 **Importer bibliothèque** : fusionne ou remplace les nœuds de votre bibliothèque actuelle avec un fichier `.json` partagé.
- 📤 **Exporter bibliothèque** : génère un `.json` portable pour partager vos nœuds.
- ✏️ **Édition d'un nœud** : la modification d'un nœud dans la bibliothèque se répercute désormais sur ses occurrences déjà posées sur le canvas.
- ✅ **Filtre vérifié / non vérifié** : la plupart des nœuds livrés ont été générés par IA et marqués comme **non vérifiés** — testez-les avant de les considérer comme fiables.

---

## ▶️ Exécution & export

### Exécution depuis l'interface

- ▶️ **Lancer** ouvre une boîte de dialogue qui demande les fichiers d'entrée (sauf si le workflow n'en attend pas).
- 🎬 Le script est écrit dans un dossier temporaire, exécuté via `cmd.exe /c` (Batch), `bash` ou `powershell.exe -ExecutionPolicy Bypass`.
- 🟢 Les nœuds passent en surbrillance pendant leur exécution et basculent en vert (succès) ou rouge (erreur).
- 📟 La sortie standard du process apparaît en direct dans la console.
- ⏹️ **Stop** envoie un kill au process en cours.

### Export pour usage externe

- 💾 **Fichier ➜ Exporter le script** génère un fichier autonome (`.bat`, `.sh` ou `.ps1`) que vous pouvez :
  - Placer dans `shell:sendto` pour l'avoir dans le menu **Envoyer vers** Windows.
  - Glisser sur l'Explorateur pour traitement direct.
  - Distribuer à un collègue (les chemins d'outils sont absolus s'ils ont été configurés ainsi).

---

## 💡 Exemples de nœuds

### 🖼️ ImageMagick — Redimensionner Max

```
magick {input} -resize {width}x{height} {output}
```

### 🎞️ HandBrakeCLI — ISO ➜ MKV

```
HandBrakeCLI -i {input} -o {output} --format av_mkv --encoder {Encodeur} --encoder-preset p4 --quality {Qualité} --all-audio --all-subtitles --aencoder {AudioEncodeur} --subtitle-burned=none --main-feature --min-duration {Durée min} --maxWidth {Largeur Max} --maxHeight {Hauteur Max} --loose-anamorphic --comb-detect --decomb
```

---

## 🌊 Exemples de flux

### 💧 Watermark v1 — basique

![CLI10](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI10.png)

Utilise **ffmpeg**.

1. Demande à l'utilisateur la taille du watermark en % de l'image.
2. Récupère hauteur et largeur de l'image source ➜ deux variables globales.
3. Redimensionne le watermark selon le %.
4. L'incruste en bas à droite (10 px de marge).
5. Sauvegarde en PNG suffixé `-WM`.

### 💧 Watermark v2 — adaptatif (orientation)

![CLI18](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI18.png)

Le nœud **Math SI** détecte si l'image est **horizontale** (largeur ≥ hauteur) ➜ `horizontal.png`, sinon ➜ `vertical.png`.

### 💧 Watermark v3 — trois cas

![CLI20](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI20.png)

Avec **Math SI if elseif**, on couvre trois orientations possibles avec un watermark dédié à chacune.

### ✏️ Vectorisation

![CLI06](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI06.png)

Utilise **ImageMagick** + **Potrace**.

1. Demande qualité (px) et seuil de coupure (gris).
2. Conversion en BMP.
3. Redimensionnement.
4. Vectorisation en SVG via Potrace.
5. Sauvegarde en SVG sous le nom d'origine.

📸 Variante avancée — vectoriser une photo couleur en cinq passes (couleur, N&B, canaux R/G/B) :

![CLI08](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI08.png)

### 🎵 Image modifiée par traitement audio (esthétique TV analogique)

![CLI09](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI09.png)

Utilise **ffmpeg**, **ImageMagick**, **sox** et des **scripts Python persos**.

1. Demande la taille finale.
2. Récupère la résolution d'origine.
3. Sépare l'image en 3 fichiers (R/G/B).
4. Chaque canal devient un spectrogramme audio FLAC.
5. Chaque audio reçoit un écho différent.
6. Reconstruit deux images à partir des spectrogrammes (résolution d'origine + résolution demandée).

### 🎬 ISO/Remux ➜ MKV

![CLI17](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI17.png)

Utilise **HandBrake-CLI**.

### 🥁 Calcul du BPM v1

![CLI23](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI23.png)

Le BPM Counter ne comprend que **WAV** et **MP3**. On convertit donc d'abord en MP3, on calcule le BPM, puis selon le format final on inscrit le tag (FFmpeg pour MP3, **metaflac** pour FLAC car FFmpeg gère mal les tags FLAC).

### 🥁 Calcul du BPM v2 (avec Merge)

![CLI24](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI24.png)

Refactorisation de la v1 : un seul appel **Calcul BPM** + un **Merge** après le Switch ➜ une seule branche `Fichier Destination` au lieu de deux. Plus DRY.

### 💻 Inventaire système ➜ HTML

![CLI25](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/cli25.png)

Créez un fichier HTML vide et lancez le script dessus : il sera transformé en page listant tous vos logiciels installés.

![CLI26](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/cli26.png)

### 📺 Téléchargement YouTube en lot

![CLI27](https://github.com/VanlindtMarc/CLI-Node-Editor/blob/main/README/CLI27.png)

Le nœud **Liste** ingère un `.txt` d'URL. Pour chaque URL : récupération auteur + titre via **yt-dlp**, puis téléchargement audio en MP3 sous `Auteur - Titre.mp3`.

---

## 🛠️ Compilation avec PyInstaller

### `Terminal Architect.spec` recommandé

```python
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['Terminal Architect.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('node_library.json',                  '.'),
        ('dependencies.json',                  '.'),
        ('AIDE.md',                            '.'),
        ('Terminal Architect ICON final.png',  '.'),
    ],
    hiddenimports=[
        'cli_node_editor',
        'cli_node_editor.core',
        'cli_node_editor.dialogs',
        'cli_node_editor.graphics',
        'cli_node_editor.script_generation',
        'cli_node_editor.highlighter',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='Terminal Architect',
    debug=False,
    upx=True,
    console=False,
    icon=['Terminal Architect ICON final.png'],
)
```

### Build

```bash
pyinstaller "Terminal Architect.spec" --clean --noconfirm
```

L'exécutable est généré dans `dist/Terminal Architect.exe`.

> 🧨 **Attention aux chemins** : PyInstaller extrait les `datas` dans un dossier temporaire (`sys._MEIPASS`). Pour les fichiers que l'app **modifie** (`dependencies.json`, `node_library.json`, `recent_workflows.json`), il faut les copier au premier lancement vers un emplacement persistant **à côté de l'exe** — sinon les modifications sont perdues à la fermeture. Voir la fonction `user_file()` dans `Terminal Architect.py`.

---

## 📂 Fichiers de configuration

| Fichier | Rôle | Modifiable |
|---|---|---|
| 📦 `node_library.json` | Bibliothèque complète des nœuds personnalisés | ✅ |
| 🔧 `dependencies.json` | Outils CLI déclarés (nom court ➜ chemin) | ✅ |
| 🕒 `recent_workflows.json` | 16 derniers workflows ouverts | ✅ |
| 📖 `AIDE.md` | Aide intégrée, accessible depuis le menu | 📌 (livré) |
| 🎨 `Terminal Architect ICON final.png` | Icône de l'application | 📌 (livré) |

En version compilée, ces fichiers se trouvent **à côté de l'exécutable**.

---

## 🪲 Bugs connus

- ✏️ Lors de la modification d'un paramètre de nœud, il faut **réécrire entièrement** la valeur — bug d'édition partielle.
- 🚧 Lancer un flux contenant des **questions utilisateur** depuis l'interface bloque l'exécution (la console d'exécution n'est pas interactive).
- 💥 La fonction « Tester tous les outils » plante si un outil n'a pas de `version_arg`.
- 🎨 Le sélecteur de couleur ne reprend pas la couleur déjà attribuée au nœud lors de la modification.

---

## 🚀 Roadmap

- 🖱️ Clic droit sur un nœud ➜ remplacement direct par un autre.
- 🧾 Encart de remarque dans les scripts générés contenant le flux source — pour pouvoir **réimporter** un workflow depuis un script déjà généré.
- 🔗 Colonne **URL** pour le gestionnaire d'outils.
- ⬇️ Téléchargement automatique des outils manquants.
- ✅ Exécuter les tests d'outils uniquement sur ceux qui ont un `version_arg` défini.
- 🔁 Remplacer un flux par un autre s'ils ont le même nombre de ports d'E/S.
- 📦 Import / export d'un nœud unique.
- 🖼️ Export du flux en **PNG** (fond transparent) et en **SVG**.

---

## 📜 Liste des CLI compatibles

| Outil | Usage principal |
|---|---|
| 🗜️ **7-Zip** | Compression / décompression |
| 🥁 **BPM Counter** | Calcul précis du BPM (WAV, MP3) |
| 🌐 **curl** | Transferts URL |
| 🏷️ **exiftool** | Métadonnées |
| 🎬 **FFmpeg** | Audio / image / vidéo (couteau suisse) |
| 🎵 **flac** | Encodeur FLAC |
| 📺 **HandBrake-CLI** | Encodage vidéo |
| 🎙️ **lame** | Encodeur MP3 |
| 🖼️ **ImageMagick** (`magick`) | Manipulation d'images |
| 🏷️ **metaflac** | Métadonnées FLAC |
| 📐 **OpenSCAD** | Modélisation 2D / 3D |
| 📄 **Pandoc** | Conversion de documents |
| ✒️ **Potrace** | Vectorisation bitmap ➜ SVG |
| 🧮 **Qalculate** | Calculatrice (valeurs non-entières) |
| 🎚️ **sox** | Traitement audio |
| 👁️ **Tesseract** | OCR |
| 🗣️ **Whisper** | Transcription audio ➜ texte/sous-titres |
| 📥 **yt-dlp** | Téléchargement YouTube et autres |

---

<sub>🏗️ Terminal Architect — un éditeur nodal pour gens pressés qui aiment quand même bien comprendre ce que leur shell fabrique.</sub>
