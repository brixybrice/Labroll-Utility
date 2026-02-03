#!/bin/bash

# Activer l'environnement virtuel
source ~/PycharmProjects/pyside2/venv3/bin/activate

# Aller dans le dossier du projet
cd ~/PycharmProjects/pyside2/labrollUtility

# Nettoyer les builds précédents
fbs clean

# Remplacer base.json par mac.json temporairement
cp mac.json src/build/settings/base.json

# Congélation et création de l'installeur
fbs freeze
fbs installer