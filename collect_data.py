#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module de collecte de données système pour MCP_AI_Monitor.
Enregistre l'utilisation CPU et RAM à intervalles réguliers dans un fichier CSV.
"""

import os
import time
import csv
import psutil
from datetime import datetime
from colorama import init, Fore, Style, Back

# Initialiser colorama
init(autoreset=True)

# Constantes
DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "data.csv")
INTERVAL = 5  # secondes

def setup_data_dir():
    """Crée le répertoire de données s'il n'existe pas."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"{Fore.GREEN}Répertoire '{DATA_DIR}' créé.")

def collect_system_data():
    """Collecte les données d'utilisation CPU et RAM."""
    cpu_percent = psutil.cpu_percent(interval=1)
    ram_percent = psutil.virtual_memory().percent
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return {
        "timestamp": timestamp,
        "cpu_percent": cpu_percent,
        "ram_percent": ram_percent
    }

def save_to_csv(data, first_write=False):
    """Sauvegarde les données dans un fichier CSV."""
    file_exists = os.path.isfile(DATA_FILE)
    
    with open(DATA_FILE, mode='a', newline='') as file:
        fieldnames = ["timestamp", "cpu_percent", "ram_percent"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        
        if first_write or not file_exists:
            writer.writeheader()
        
        writer.writerow(data)

def main():
    """Fonction principale pour la collecte de données."""
    setup_data_dir()
    first_write = not os.path.isfile(DATA_FILE)
    
    print(f"{Fore.CYAN}MCP_AI_Monitor: Collecte de données système démarrée...")
    print(f"{Fore.CYAN}Intervalle: {INTERVAL} secondes")
    print(f"{Fore.GREEN}Données sauvegardées dans: {DATA_FILE}")
    print(f"{Fore.YELLOW}Appuyez sur Ctrl+C pour arrêter.")
    
    # Compteur pour suivre le nombre d'échantillons collectés
    samples_count = 0
    start_time = time.time()
    
    try:
        while True:
            data = collect_system_data()
            save_to_csv(data, first_write)
            first_write = False
            samples_count += 1
            
            # Déterminer la couleur en fonction des valeurs
            cpu_color = Fore.GREEN
            ram_color = Fore.GREEN
            
            if data['cpu_percent'] > 80:
                cpu_color = Fore.RED
            elif data['cpu_percent'] > 50:
                cpu_color = Fore.YELLOW
                
            if data['ram_percent'] > 80:
                ram_color = Fore.RED
            elif data['ram_percent'] > 50:
                ram_color = Fore.YELLOW
            
            # Affichage avec couleurs
            print(f"[{Fore.CYAN}{data['timestamp']}{Style.RESET_ALL}] "
                  f"CPU: {cpu_color}{data['cpu_percent']}%{Style.RESET_ALL}, "
                  f"RAM: {ram_color}{data['ram_percent']}%{Style.RESET_ALL} "
                  f"({Fore.MAGENTA}#{samples_count}{Style.RESET_ALL})")
            
            time.sleep(INTERVAL)
    except KeyboardInterrupt:
        elapsed_time = time.time() - start_time
        print(f"\n{Fore.YELLOW}Collecte de données arrêtée.")
        print(f"{Fore.GREEN}{samples_count} échantillons collectés en {elapsed_time:.1f} secondes.")

if __name__ == "__main__":
    main() 