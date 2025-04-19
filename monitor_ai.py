#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Module de surveillance en temps réel avec IA pour MCP_AI_Monitor.
Détecte les anomalies dans l'utilisation CPU/RAM et envoie des alertes.
"""

import os
import time
import joblib
import psutil
import numpy as np
import pandas as pd
from datetime import datetime
from plyer import notification
from colorama import init, Fore, Style, Back

# Initialiser colorama
init(autoreset=True)

# Constantes
MODEL_DIR = "model"
MODEL_FILE = os.path.join(MODEL_DIR, "mcp_model.pkl")
FEATURE_NAMES_FILE = os.path.join(MODEL_DIR, "feature_names.pkl")
HISTORY_SIZE = 20  # Nombre de points de données à conserver dans l'historique
INTERVAL = 5  # secondes
ALERT_COOLDOWN = 60  # secondes entre les alertes

# Seuils pour les ressources système
CPU_THRESHOLD = 80  # Seuil d'utilisation CPU considéré comme élevé (%)
RAM_THRESHOLD = 80  # Seuil d'utilisation RAM considéré comme élevé (%)
# Périodes d'apprentissage et d'adaptation
LEARNING_PERIOD = 10  # Nombre de points de données à collecter avant d'activer les alertes
ADAPTATION_FACTOR = 0.8  # Facteur pour adapter les seuils en fonction de l'utilisation normale

class MCPMonitor:
    """Classe principale pour la surveillance du système avec IA."""
    
    def __init__(self):
        """Initialise le moniteur MCP."""
        self.model = self._load_model()
        self.feature_names = self._load_feature_names()
        self.last_alert_time = 0
        self.data_history = []
        self.learning_data = []
        self.anomaly_scores = []
        # Pour la détection d'anomalies adaptative
        self.anomaly_threshold = -0.15  # Seuil de base pour les scores d'anomalies (moins négatif = plus sensible)
        self.baseline_cpu = None
        self.baseline_ram = None
        self.is_learning = True
        self.known_apps = {}  # Pour mémoriser les applications connues et leur impact
        
    def _load_model(self):
        """Charge le modèle IA depuis le fichier."""
        if not os.path.exists(MODEL_FILE):
            print(f"{Fore.RED}Erreur: Le modèle {MODEL_FILE} n'existe pas. Exécutez train_model.py d'abord.")
            raise FileNotFoundError(f"Le modèle {MODEL_FILE} n'existe pas. Exécutez train_model.py d'abord.")
        
        model = joblib.load(MODEL_FILE)
        print(f"{Fore.GREEN}Modèle chargé depuis: {MODEL_FILE}")
        return model
    
    def _load_feature_names(self):
        """Charge les noms des caractéristiques depuis le fichier."""
        if not os.path.exists(FEATURE_NAMES_FILE):
            print(f"{Fore.YELLOW}Attention: Fichier de noms de caractéristiques non trouvé. Utilisation de noms par défaut.")
            return ["cpu_percent", "ram_percent"]
        
        feature_names = joblib.load(FEATURE_NAMES_FILE)
        print(f"{Fore.GREEN}Noms des caractéristiques chargés depuis: {FEATURE_NAMES_FILE}")
        return feature_names
    
    def collect_current_data(self):
        """Collecte les données système actuelles."""
        cpu_percent = psutil.cpu_percent(interval=1)
        ram_percent = psutil.virtual_memory().percent
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Récupérer plus d'informations pour un diagnostic plus détaillé
        cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
        ram_used = psutil.virtual_memory().used / (1024 * 1024 * 1024)  # En Go
        ram_total = psutil.virtual_memory().total / (1024 * 1024 * 1024)  # En Go
        
        # Récupérer les processus actifs (pour identifier les applications ouvertes)
        active_processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                pinfo = proc.info
                if pinfo['cpu_percent'] > 1.0 or pinfo['memory_percent'] > 1.0:  # Filtrer les processus actifs
                    active_processes.append(pinfo)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # Trier par utilisation CPU
        active_processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
        
        data = {
            "timestamp": timestamp,
            "cpu_percent": cpu_percent,
            "ram_percent": ram_percent,
            "cpu_per_core": cpu_per_core,
            "ram_used": round(ram_used, 2),
            "ram_total": round(ram_total, 2),
            "active_processes": active_processes[:5]  # Top 5 processus
        }
        
        # Ajouter à l'historique et limiter sa taille
        self.data_history.append(data)
        if len(self.data_history) > HISTORY_SIZE:
            self.data_history.pop(0)
        
        # Si nous sommes en phase d'apprentissage, ajoutons à learning_data
        if len(self.learning_data) < LEARNING_PERIOD:
            self.learning_data.append(data)
            # Si nous avons assez de données d'apprentissage, calculer les valeurs de référence
            if len(self.learning_data) == LEARNING_PERIOD:
                self._calculate_baselines()
                self.is_learning = False
                print(f"{Fore.CYAN}Phase d'apprentissage terminée. Référence CPU: {self.baseline_cpu:.1f}%, RAM: {self.baseline_ram:.1f}%")
        
        return data
    
    def _calculate_baselines(self):
        """Calcule les valeurs de référence à partir des données d'apprentissage."""
        if not self.learning_data:
            return
        
        # Calculer la moyenne et l'écart-type de l'utilisation CPU et RAM
        cpu_values = [d["cpu_percent"] for d in self.learning_data]
        ram_values = [d["ram_percent"] for d in self.learning_data]
        
        self.baseline_cpu = np.mean(cpu_values)
        self.baseline_ram = np.mean(ram_values)
        self.cpu_std = np.std(cpu_values) if len(cpu_values) > 1 else 5.0
        self.ram_std = np.std(ram_values) if len(ram_values) > 1 else 5.0
        
        # Ajuster le seuil d'anomalie en fonction des données d'apprentissage
        # Plus la variance est élevée, plus le seuil doit être bas
        variance_factor = min(1.0, max(0.1, 0.5 / (self.cpu_std / 10.0)))
        self.anomaly_threshold = -0.15 * variance_factor

    def is_application_launch(self, data):
        """Détecte si un changement soudain est dû au lancement d'une application connue."""
        if not data.get("active_processes"):
            return False, None
        
        # Vérifier si un nouveau processus avec une utilisation CPU importante est apparu
        for proc in data["active_processes"]:
            proc_name = proc["name"]
            if proc_name not in self.known_apps and proc["cpu_percent"] > 10:
                # C'est potentiellement une nouvelle application
                return True, proc_name
            
        return False, None
    
    def learn_application_impact(self, app_name, impact_cpu, impact_ram):
        """Mémorise l'impact d'une application sur les ressources système."""
        self.known_apps[app_name] = {
            "cpu_impact": impact_cpu,
            "ram_impact": impact_ram,
            "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        print(f"{Fore.CYAN}Application mémorisée: {app_name} (Impact CPU: {impact_cpu:.1f}%, RAM: {impact_ram:.1f}%)")

    def detect_anomaly(self, data):
        """Détecte si les données actuelles représentent une anomalie."""
        # En phase d'apprentissage, pas d'alerte d'anomalie
        if self.is_learning:
            return False, 0.0
            
        # Créer un DataFrame avec les noms de caractéristiques
        features_df = pd.DataFrame([[data["cpu_percent"], data["ram_percent"]]], 
                                  columns=self.feature_names)
        
        # Faire la prédiction
        prediction = self.model.predict(features_df)[0]
        score = self.model.score_samples(features_df)[0]
        
        # Ajouter le score à l'historique
        self.anomaly_scores.append(score)
        if len(self.anomaly_scores) > HISTORY_SIZE:
            self.anomaly_scores.pop(0)
        
        # Récupérer les seuils adaptés aux valeurs de référence
        cpu_anomaly_threshold = min(CPU_THRESHOLD, self.baseline_cpu * 2) if self.baseline_cpu else CPU_THRESHOLD
        ram_anomaly_threshold = min(RAM_THRESHOLD, self.baseline_ram * 2) if self.baseline_ram else RAM_THRESHOLD
        
        # Détecter si un lancement d'application a eu lieu
        app_launch, app_name = self.is_application_launch(data)
        
        # Si c'est un lancement d'application, calculer l'impact
        if app_launch and len(self.data_history) > 1:
            prev_data = self.data_history[-2]
            cpu_impact = data["cpu_percent"] - prev_data["cpu_percent"]
            ram_impact = data["ram_percent"] - prev_data["ram_percent"]
            
            if cpu_impact > 10 or ram_impact > 5:  # Impact significatif
                self.learn_application_impact(app_name, cpu_impact, ram_impact)
                # On ne considère pas cela comme une anomalie
                return False, score
        
        # Critères pour une vraie anomalie:
        # 1. Le modèle prédit une anomalie (score < seuil) ET
        # 2. Soit l'utilisation CPU est anormalement élevée, soit l'utilisation RAM est anormalement élevée
        is_cpu_high = data["cpu_percent"] > cpu_anomaly_threshold
        is_ram_high = data["ram_percent"] > ram_anomaly_threshold

        # Les seuils sont dynamiquement adaptés en fonction des valeurs de référence
        is_cpu_spike = False
        is_ram_spike = False
        
        if self.baseline_cpu is not None and self.cpu_std is not None:
            is_cpu_spike = data["cpu_percent"] > (self.baseline_cpu + 2 * self.cpu_std)
            
        if self.baseline_ram is not None and self.ram_std is not None:
            is_ram_spike = data["ram_percent"] > (self.baseline_ram + 2 * self.ram_std)
            
        # Une anomalie est soit un pic dans les ressources, soit une valeur absolue élevée
        resources_anomaly = is_cpu_high or is_ram_high or is_cpu_spike or is_ram_spike
        
        # Anomalie si 1) le score est faible ET 2) ressources anormales
        is_anomaly = (score < self.anomaly_threshold) and resources_anomaly
        
        return is_anomaly, score
    
    def get_trend_info(self):
        """Calcule les tendances à partir de l'historique des données."""
        if len(self.data_history) < 2:
            return "Pas assez de données pour calculer la tendance."
        
        current = self.data_history[-1]
        previous = self.data_history[0]
        
        cpu_change = current["cpu_percent"] - previous["cpu_percent"]
        ram_change = current["ram_percent"] - previous["ram_percent"]
        
        duration = min(len(self.data_history) * INTERVAL, HISTORY_SIZE * INTERVAL)
        
        trend_info = f"Tendance (sur {duration}s):\n"
        trend_info += f"CPU: {'↑' if cpu_change > 0 else '↓'} {abs(cpu_change):.1f}%\n"
        trend_info += f"RAM: {'↑' if ram_change > 0 else '↓'} {abs(ram_change):.1f}%"
        
        return trend_info
    
    def format_score_explanation(self, score):
        """Fournit une explication du score d'anomalie."""
        if score > -0.05:
            return f"{Fore.GREEN}Normal"
        elif score > -0.15:
            return f"{Fore.CYAN}Légèrement inhabituel"
        elif score > -0.3:
            return f"{Fore.YELLOW}Inhabituel"
        elif score > -0.5:
            return f"{Fore.MAGENTA}Très inhabituel"
        else:
            return f"{Fore.RED}Extrêmement anormal"
            
    def send_alert(self, data, score):
        """Envoie une alerte en cas d'anomalie détectée."""
        current_time = time.time()
        
        # Vérification du délai de refroidissement
        if current_time - self.last_alert_time < ALERT_COOLDOWN:
            return
        
        # Récupérer les informations supplémentaires
        trend_info = self.get_trend_info()
        top_processes = self.get_top_processes()
        
        title = "MCP_AI_Monitor: Anomalie Détectée"
        message = f"CPU: {data['cpu_percent']}%, RAM: {data['ram_percent']}%\n"
        message += f"Score d'anomalie: {score:.4f}\n"
        message += f"{trend_info}\n\n"
        message += f"Processus les plus gourmands:\n{top_processes}"
        
        # Version courte pour la notification
        short_message = f"CPU: {data['cpu_percent']}%, RAM: {data['ram_percent']}%\nScore: {score:.4f}"
        
        # Envoi de la notification
        notification.notify(
            title=title,
            message=short_message,
            app_name="MCP_AI_Monitor",
            timeout=10
        )
        
        print(f"\n{Back.RED}{Fore.WHITE}[ALERTE] {title}{Style.RESET_ALL}")
        print(f"{Fore.RED}[ALERTE] {message}")
        
        self.last_alert_time = current_time
    
    def get_top_processes(self, n=3):
        """Récupère les processus qui consomment le plus de ressources."""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                pinfo = proc.info
                processes.append(pinfo)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # Trier par utilisation CPU puis RAM
        processes.sort(key=lambda x: (x['cpu_percent'], x['memory_percent']), reverse=True)
        
        result = ""
        for i, proc in enumerate(processes[:n]):
            result += f"{proc['name']} (PID: {proc['pid']}): CPU {proc['cpu_percent']:.1f}%, MEM {proc['memory_percent']:.1f}%\n"
        
        return result
    
    def start_monitoring(self):
        """Démarre la surveillance en temps réel."""
        print(f"{Fore.CYAN}MCP_AI_Monitor: Surveillance en temps réel démarrée...")
        print(f"{Fore.CYAN}Intervalle: {INTERVAL} secondes")
        print(f"{Fore.YELLOW}Phase d'apprentissage: {Fore.WHITE}{LEARNING_PERIOD} échantillons")
        print(f"{Fore.YELLOW}Appuyez sur Ctrl+C pour arrêter.")
        
        try:
            while True:
                # Collecte des données
                data = self.collect_current_data()
                
                # Détection d'anomalies
                is_anomaly, score = self.detect_anomaly(data)
                
                # Formater le status avec code couleur
                if self.is_learning:
                    status = f"{Fore.BLUE}APPRENTISSAGE"
                elif is_anomaly:
                    status = f"{Back.RED}{Fore.WHITE}ANOMALIE"
                else:
                    status = f"{Fore.GREEN}normal"
                
                # Formater le score
                score_explanation = self.format_score_explanation(score)
                
                # Affichage des données avec couleurs
                print(f"[{Fore.CYAN}{data['timestamp']}{Style.RESET_ALL}] "
                      f"CPU: {Fore.YELLOW}{data['cpu_percent']}%{Style.RESET_ALL}, "
                      f"RAM: {Fore.MAGENTA}{data['ram_percent']}%{Style.RESET_ALL} - "
                      f"{status}{Style.RESET_ALL} "
                      f"(score: {score:.4f} - {score_explanation}{Style.RESET_ALL})")
                
                # Envoi d'alerte si anomalie
                if is_anomaly:
                    self.send_alert(data, score)
                
                time.sleep(INTERVAL)
        
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}Surveillance arrêtée.{Style.RESET_ALL}")

def main():
    """Fonction principale pour la surveillance IA."""
    try:
        monitor = MCPMonitor()
        monitor.start_monitoring()
    except Exception as e:
        print(f"{Fore.RED}Erreur lors de la surveillance: {str(e)}")

if __name__ == "__main__":
    main() 