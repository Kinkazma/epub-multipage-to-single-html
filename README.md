# epub-multipage-to-single-html

Outil en ligne de commande en Python qui convertit un ePub à **mise en page fixe**
(fixed-layout, par exemple exporté depuis Apple Pages) en **un seul fichier HTML** :

- toutes les pages (`page-1.xhtml`, `page-2.xhtml`, …) sont empilées verticalement,
- la mise en page absolue de chaque page est préservée (fac-similé),
- les images, GIF animés et polices sont encodés en **data URI base64**,
- le résultat est un **HTML autonome** (aucune ressource externe nécessaire).

## Fonctionnalités

- Décompression automatique de l’ePub (ZIP) dans un dossier temporaire
- Détection des fichiers `page-*.xhtml` et tri dans l’ordre naturel
- Correction des balises autofermantes non valides en HTML (`<div />` → `<div></div>`)
- Intégration des polices (`.ttf`, `.otf`, `.woff`, `.woff2`) en data URI
- Intégration des images (`.png`, `.gif`, `.jpg`, `.jpeg`) en data URI
- Génération d’un conteneur `.page` par page, avec dimensions et ombre portée
- Liens internes `href="page-N.xhtml"` réécrits en ancres `href="#page-N"`

## Utilisation rapide

```bash
python3 epub_to_html.py MonLivre.epub
# → génère MonLivre.html dans le même dossier

python3 epub_to_html.py MonLivre.epub /chemin/vers/sortie.html
# → nom de fichier de sortie personnalisé
