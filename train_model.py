#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module d'entraînement du modèle IA pour MCP_AI_Monitor.
Utilise Isolation Forest pour détecter les anomalies dans l'utilisation CPU/RAM.
"""

import os
import pandas as pd
import numpy as np
from sklearn.ensemble import IsolationForest
import joblib
from colorama import init, Fore, Style, Back

# Initialiser colorama
init(autoreset=True)

# Constantes
DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "data.csv")
MODEL_DIR = "model"
MODEL_FILE = os.path.join(MODEL_DIR, "mcp_model.pkl")
FEATURE_NAMES_FILE = os.path.join(MODEL_DIR, "feature_names.pkl")
CONTAMINATION = 0.05  # 5% des données considérées comme anomalies

def setup_model_dir():
    """Crée le répertoire pour le modèle s'il n'existe pas."""
    if not os.path.exists(MODEL_DIR):
        os.makedirs(MODEL_DIR)
        print(f"{Fore.GREEN}Répertoire '{MODEL_DIR}' créé.")

def load_data():
    """Charge les données depuis le fichier CSV."""
    if not os.path.exists(DATA_FILE):
        error_msg = f"Le fichier de données {DATA_FILE} n'existe pas. Exécutez collect_data.py d'abord."
        print(f"{Fore.RED}{error_msg}")
        raise FileNotFoundError(error_msg)
    
    df = pd.read_csv(DATA_FILE)
    
    if len(df) < 50:
        print(f"{Fore.YELLOW}Attention: Moins de 50 échantillons disponibles. Le modèle pourrait être moins précis.")
    
    print(f"{Fore.GREEN}Données chargées : {len(df)} échantillons")
    return df

def preprocess_data(df):
    """Prétraite les données pour l'entraînement."""
    # On utilise seulement les colonnes numériques pour l'entraînement
    features = df[["cpu_percent", "ram_percent"]]
    
    # Statistiques descriptives
    print(f"\n{Fore.CYAN}Statistiques des données:")
    
    # Formatage coloré des statistiques
    stats = features.describe()
    print(f"{Fore.YELLOW}{'='*60}")
    print(f"{Fore.WHITE}{'':15} {'CPU (%)':15} {'RAM (%)':15}")
    print(f"{Fore.YELLOW}{'='*60}")
    
    for stat in ['count', 'mean', 'std', 'min', '25%', '50%', '75%', 'max']:
        cpu_value = stats['cpu_percent'][stat]
        ram_value = stats['ram_percent'][stat]
        
        # Coloration conditionnelle pour les valeurs
        cpu_color = Fore.WHITE
        ram_color = Fore.WHITE
        
        if stat == 'max':
            cpu_color = Fore.RED if cpu_value > 80 else (Fore.YELLOW if cpu_value > 50 else Fore.GREEN)
            ram_color = Fore.RED if ram_value > 80 else (Fore.YELLOW if ram_value > 50 else Fore.GREEN)
        elif stat == 'mean':
            cpu_color = Fore.RED if cpu_value > 60 else (Fore.YELLOW if cpu_value > 30 else Fore.GREEN)
            ram_color = Fore.RED if ram_value > 60 else (Fore.YELLOW if ram_value > 30 else Fore.GREEN)
        
        # Formatage selon le type de statistique
        if stat in ['count']:
            print(f"{Fore.CYAN}{stat:15} {cpu_value:15.0f} {ram_value:15.0f}")
        else:
            print(f"{Fore.CYAN}{stat:15} {cpu_color}{cpu_value:15.2f}{Style.RESET_ALL} {ram_color}{ram_value:15.2f}{Style.RESET_ALL}")
    
    print(f"{Fore.YELLOW}{'='*60}")
    
    return features

def train_model(features):
    """Entraîne le modèle Isolation Forest."""
    print(f"\n{Fore.CYAN}Entraînement du modèle Isolation Forest...")
    
    # Création du modèle
    model = IsolationForest(
        n_estimators=100,
        max_samples='auto',
        contamination=CONTAMINATION,
        random_state=42,
        verbose=0
    )
    
    print(f"{Fore.YELLOW}Configuration du modèle:")
    print(f"{Fore.WHITE}  - Arbres: 100")
    print(f"{Fore.WHITE}  - Échantillons: auto")
    print(f"{Fore.WHITE}  - Contamination: {CONTAMINATION*100:.1f}%")
    
    # Marqueur de progression simple
    print(f"{Fore.YELLOW}Progression: ", end='')
    
    # Entraînement
    model.fit(features)
    print(f"{Fore.GREEN}Terminé!")
    
    # Évaluation sur les données d'entraînement
    predictions = model.predict(features)
    anomalies = predictions == -1
    anomaly_count = np.sum(anomalies)
    anomaly_percent = (anomaly_count / len(features)) * 100
    
    print(f"{Fore.GREEN}Modèle entraîné avec succès.")
    
    # Affichage coloré des résultats
    print(f"{Fore.CYAN}Anomalies détectées dans les données d'entraînement: "
          f"{Fore.YELLOW}{anomaly_count} sur {len(features)} "
          f"({Fore.MAGENTA}{anomaly_percent:.1f}%{Fore.CYAN})")
    
    return model

def save_model(model, feature_names):
    """Sauvegarde le modèle entraîné et les noms des caractéristiques."""
    setup_model_dir()
    joblib.dump(model, MODEL_FILE)
    joblib.dump(feature_names, FEATURE_NAMES_FILE)
    print(f"{Fore.GREEN}Modèle sauvegardé dans: {Fore.CYAN}{MODEL_FILE}")
    print(f"{Fore.GREEN}Noms des caractéristiques sauvegardés dans: {Fore.CYAN}{FEATURE_NAMES_FILE}")

def main():
    """Fonction principale pour l'entraînement du modèle."""
    print(f"{Fore.CYAN}MCP_AI_Monitor: Entraînement du modèle IA démarré...")
    
    try:
        # Afficher une barre de progression simple
        print(f"{Fore.YELLOW}{'='*60}")
        print(f"{Fore.WHITE}Phase 1/3: Chargement des données...")
        
        # Charger et prétraiter les données
        df = load_data()
        
        print(f"{Fore.WHITE}Phase 2/3: Prétraitement des données...")
        features = preprocess_data(df)
        
        print(f"{Fore.WHITE}Phase 3/3: Entraînement du modèle...")
        # Entraîner le modèle
        model = train_model(features)
        
        # Sauvegarder le modèle et les noms des caractéristiques
        feature_names = list(features.columns)
        save_model(model, feature_names)
        
        print(f"\n{Fore.GREEN}{'='*60}")
        print(f"{Fore.GREEN}Entraînement terminé avec succès.")
        print(f"{Fore.GREEN}{'='*60}")
        
    except Exception as e:
        print(f"{Fore.RED}Erreur lors de l'entraînement du modèle: {str(e)}")

if __name__ == "__main__":
    main() 