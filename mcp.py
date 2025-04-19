#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script principal pour MCP_AI_Monitor.
Permet de lancer les différents modules du système.
"""

import os
import sys
import argparse
import subprocess
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from datetime import datetime
from colorama import init, Fore, Style, Back
from discord_webhook import DiscordWebhook, DiscordEmbed
import socket
import platform
import psutil
import time
import json

# Initialiser colorama
init(autoreset=True)

# Configuration des webhooks Discord par catégorie
# Webhook pour les rapports système (infos générales, CPU/RAM, processus)
DISCORD_HARDWARE_WEBHOOK_URL = "https://discord.com/api/webhooks/1362970830145060935/8Nah3zbLG14ciJPLGQL_fdyn4u8UA0GAgt1C9cpuL_LbaiLjt4TZccjso6AXnPLvXyj3"

# Webhook pour les rapports réseau (infos réseau, connexions, interfaces)
DISCORD_NETWORK_WEBHOOK_URL = "https://discord.com/api/webhooks/1362971345369170092/h9KNZNbiEsBKzqFa4ExDoK_qNMfrUNkXBWNuz2jyYS9ide72qLzNrBJk7f6bbHyy_SvU"

# Webhook général (conservé pour compatibilité)
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1362961722029117510/kxWuQpy-lPbaGbX4-nk3_2eEMRamP50kckEmrCxBEBXtq5EMy006C0iW8IpxtX51yExs"

def print_banner():
    """Affiche la bannière MCP."""
    banner = r"""
    __  _______________        ___    ____    __  ___            _ __            
   /  |/  / ____/ ____/       /   |  /  _/   /  |/  /___  ____  (_) /_____  _____
  / /|_/ / /   / __/ ______  / /| |  / /    / /|_/ / __ \/ __ \/ / __/ __ \/ ___/
 / /  / / /___/ /___/_____/ / ___ |_/ /    / /  / / /_/ / / / / / /_/ /_/ / /    
/_/  /_/\____/_____/       /_/  |_/___/   /_/  /_/\____/_/ /_/_/\__/\____/_/     
                                                                                                                                                   
    """
    print(f"{Fore.CYAN}{banner}")
    print(f"{Fore.GREEN}MCP_AI_Monitor - Master Control Program")
    print(f"{Fore.GREEN}Surveillance système avec détection d'anomalies par IA")
    print(f"{Fore.YELLOW}{'='*70}")

def check_dependencies():
    """Vérifie si les dépendances sont installées."""
    try:
        import psutil
        import pandas
        import sklearn
        import joblib
        import plyer
        import matplotlib
        import colorama
        import discord_webhook
        return True
    except ImportError as e:
        print(f"{Fore.RED}Erreur: Dépendance manquante - {str(e)}")
        print(f"{Fore.YELLOW}Installez les dépendances avec: pip install -r requirements.txt")
        return False

def run_module(module_name):
    """Exécute un module Python spécifique."""
    try:
        subprocess.run([sys.executable, f"{module_name}.py"])
    except Exception as e:
        print(f"{Fore.RED}Erreur lors de l'exécution de {module_name}.py: {str(e)}")

def get_system_info():
    """Récupère les informations système pour les inclure dans les rapports."""
    hostname = socket.gethostname()
    system_info = {
        "hostname": hostname,
        "os": platform.system() + " " + platform.release(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "cpu_cores": psutil.cpu_count(logical=True),
        "physical_cores": psutil.cpu_count(logical=False),
        "ram_total": round(psutil.virtual_memory().total / (1024**3), 2)  # En Go
    }
    return system_info

def get_network_info():
    """Récupère les informations réseau."""
    net_io_start = psutil.net_io_counters()
    time.sleep(1)  # Attendre 1 seconde pour calculer la vitesse
    net_io_end = psutil.net_io_counters()
    
    # Calculer les débits
    bytes_sent = net_io_end.bytes_sent - net_io_start.bytes_sent
    bytes_recv = net_io_end.bytes_recv - net_io_start.bytes_recv
    
    # Convertir en KB/s
    kb_sent = bytes_sent / 1024
    kb_recv = bytes_recv / 1024
    
    # Récupérer les informations des interfaces réseau
    net_if_addrs = psutil.net_if_addrs()
    interfaces = []
    
    for interface_name, addresses in net_if_addrs.items():
        for addr in addresses:
            if addr.family == socket.AF_INET:  # IPv4
                interfaces.append({
                    "name": interface_name,
                    "ip": addr.address,
                    "netmask": addr.netmask
                })
    
    # Récupérer les connexions réseau actives
    connections = []
    for conn in psutil.net_connections(kind='inet'):
        if conn.status == 'ESTABLISHED':
            connections.append({
                "local_addr": f"{conn.laddr.ip}:{conn.laddr.port}",
                "remote_addr": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "N/A",
                "status": conn.status,
                "pid": conn.pid
            })
    
    # Limiter le nombre de connexions pour éviter des rapports trop longs
    connections = connections[:10]
    
    return {
        "upload_speed": kb_sent,
        "download_speed": kb_recv,
        "total_sent": net_io_end.bytes_sent / (1024**3),  # En GB
        "total_recv": net_io_end.bytes_recv / (1024**3),  # En GB
        "interfaces": interfaces,
        "connections": connections[:5]  # Limiter à 5 connexions
    }

def get_top_processes(n=5):
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
    
    return processes[:n]

def send_discord_report(report_file, stats_data):
    """Envoie le rapport à Discord via webhook avec plusieurs embeds thématiques."""
    try:
        print(f"{Fore.CYAN}Envoi du rapport sur Discord...")
        
        # Récupérer les informations système
        sys_info = get_system_info()
        
        # Récupérer les informations réseau
        net_info = get_network_info()
        
        # Récupérer les processus les plus gourmands
        top_procs = get_top_processes(5)
        
        # --------------------- RAPPORT HARDWARE ---------------------
        # Webhook pour les rapports hardware (info système, CPU/RAM, processus)
        hardware_webhook = DiscordWebhook(url=DISCORD_HARDWARE_WEBHOOK_URL, 
                                  username="MCP Rapport Hardware")
        
        # Fichier graphique à envoyer
        with open(report_file, "rb") as f:
            hardware_webhook.add_file(file=f.read(), filename=os.path.basename(report_file))
        
        # --------- EMBED 1: INFORMATIONS GÉNÉRALES ---------
        embed_info = DiscordEmbed(
            title=f"📊 Rapport MCP AI Monitor - {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            description=f"Rapport complet de surveillance système généré par MCP AI Monitor.",
            color=0x00ffff  # Cyan
        )
        
        # Ajouter les informations système
        embed_info.add_embed_field(
            name="📋 Informations Système",
            value=f"**Machine:** {sys_info['hostname']}\n"
                 f"**OS:** {sys_info['os']}\n"
                 f"**CPU:** {sys_info['processor']}\n"
                 f"**Cœurs:** {sys_info['physical_cores']} physiques / {sys_info['cpu_cores']} logiques\n"
                 f"**RAM:** {sys_info['ram_total']} Go"
        )
        
        # Ajouter le timestamp et le footer
        embed_info.set_timestamp()
        embed_info.set_footer(text="MCP AI Monitor | Vue d'ensemble")
        
        # --------- EMBED 2: GRAPHIQUE D'UTILISATION ---------
        embed_graph = DiscordEmbed(
            title=f"📈 Graphique d'Utilisation CPU/RAM",
            color=0x2ecc71  # Vert
        )
        
        # Ajouter l'image du graphique
        embed_graph.set_image(url=f"attachment://{os.path.basename(report_file)}")
        
        # Ajouter les statistiques principales
        embed_graph.add_embed_field(
            name="📊 Statistiques d'Utilisation",
            value=f"**CPU Moyen:** {stats_data['cpu_percent']['mean']:.2f}%\n"
                 f"**CPU Max:** {stats_data['cpu_percent']['max']:.2f}%\n"
                 f"**RAM Moyenne:** {stats_data['ram_percent']['mean']:.2f}%\n"
                 f"**RAM Max:** {stats_data['ram_percent']['max']:.2f}%\n"
                 f"**Échantillons:** {stats_data['count']}"
        )
        
        embed_graph.set_footer(text="MCP AI Monitor | Graphiques et statistiques")
        
        # --------- EMBED 3: PROCESSUS ---------
        embed_processes = DiscordEmbed(
            title=f"🔄 Processus les Plus Gourmands",
            description=f"Liste des processus consommant le plus de ressources système",
            color=0xe74c3c  # Rouge
        )
        
        # Tableau formaté des processus
        processes_info = ""
        for i, proc in enumerate(top_procs):
            processes_info += f"**{i+1}.** `{proc['name']}` (PID: {proc['pid']})\n"
            processes_info += f"   └─ CPU: {proc['cpu_percent']:.1f}%, RAM: {proc['memory_percent']:.1f}%\n"
        
        embed_processes.description = processes_info if processes_info else "Aucun processus actif détecté."
        embed_processes.set_footer(text="MCP AI Monitor | Processus actifs")
        
        # Ajouter les embeds au webhook hardware
        hardware_webhook.add_embed(embed_info)
        hardware_webhook.add_embed(embed_graph)
        hardware_webhook.add_embed(embed_processes)
        
        # Envoyer le webhook hardware
        hardware_response = hardware_webhook.execute()
        
        # --------------------- RAPPORT RÉSEAU ---------------------
        # Webhook pour les rapports réseau
        network_webhook = DiscordWebhook(url=DISCORD_NETWORK_WEBHOOK_URL, 
                                 username="MCP Network AI")
        
        # --------- EMBED 4: RÉSEAU ---------
        embed_network = DiscordEmbed(
            title=f"🌐 Informations Réseau",
            description=f"Rapport réseau pour **{sys_info['hostname']}** généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
            color=0x3498db  # Bleu
        )
        
        # Activité réseau
        embed_network.add_embed_field(
            name="📶 Activité Réseau",
            value=f"**Débit montant:** {net_info['upload_speed']:.2f} KB/s\n"
                 f"**Débit descendant:** {net_info['download_speed']:.2f} KB/s\n"
                 f"**Total envoyé:** {net_info['total_sent']:.2f} GB\n"
                 f"**Total reçu:** {net_info['total_recv']:.2f} GB",
            inline=True
        )
        
        # Interfaces réseau
        interfaces_info = ""
        for interface in net_info['interfaces'][:3]:  # Limiter à 3 interfaces pour la lisibilité
            interfaces_info += f"**{interface['name']}:** {interface['ip']}\n"
        
        embed_network.add_embed_field(
            name="🖧 Interfaces Réseau",
            value=interfaces_info if interfaces_info else "Aucune interface réseau active.",
            inline=True
        )
        
        embed_network.set_timestamp()
        embed_network.set_footer(text="MCP AI Monitor | Informations réseau")
        
        # Ajouter l'embed au webhook réseau
        network_webhook.add_embed(embed_network)
        
        # Envoyer le webhook réseau
        network_response = network_webhook.execute()
        
        # Vérification des résultats
        hardware_success = hardware_response.status_code >= 200 and hardware_response.status_code < 300
        network_success = network_response.status_code >= 200 and network_response.status_code < 300
        
        if hardware_success and network_success:
            print(f"{Fore.GREEN}Rapports envoyés avec succès sur Discord !")
        else:
            if not hardware_success:
                print(f"{Fore.RED}Erreur lors de l'envoi du rapport hardware: Code {hardware_response.status_code}")
            if not network_success:
                print(f"{Fore.RED}Erreur lors de l'envoi du rapport réseau: Code {network_response.status_code}")
        
    except Exception as e:
        print(f"{Fore.RED}Erreur lors de l'envoi des rapports sur Discord: {str(e)}")

def create_network_graph():
    """Crée un graphique d'utilisation réseau."""
    # Collecter des données réseau pendant 10 secondes
    network_data = []
    start_time = time.time()
    
    print(f"{Fore.CYAN}Collecte des données réseau pour le graphique...")
    
    try:
        # Collecter des données pendant ~10 secondes
        for i in range(10):
            net_io = psutil.net_io_counters()
            network_data.append({
                "timestamp": time.time() - start_time,
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv
            })
            time.sleep(1)
        
        # Calculer les débits
        for i in range(1, len(network_data)):
            sent_diff = network_data[i]["bytes_sent"] - network_data[i-1]["bytes_sent"]
            recv_diff = network_data[i]["bytes_recv"] - network_data[i-1]["bytes_recv"]
            time_diff = network_data[i]["timestamp"] - network_data[i-1]["timestamp"]
            
            network_data[i]["upload_speed"] = sent_diff / time_diff / 1024  # KB/s
            network_data[i]["download_speed"] = recv_diff / time_diff / 1024  # KB/s
        
        # Supprimer le premier point car il n'a pas de vitesse calculée
        network_data = network_data[1:]
        
        # Créer le graphique
        fig, ax = plt.subplots(figsize=(10, 6))
        
        times = [d["timestamp"] for d in network_data]
        upload_speeds = [d["upload_speed"] for d in network_data]
        download_speeds = [d["download_speed"] for d in network_data]
        
        ax.plot(times, upload_speeds, 'r-', label='Upload (KB/s)')
        ax.plot(times, download_speeds, 'b-', label='Download (KB/s)')
        
        ax.set_title('Utilisation Réseau', fontsize=16, fontweight='bold')
        ax.set_xlabel('Temps (secondes)', fontsize=12)
        ax.set_ylabel('Vitesse (KB/s)', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # Créer le répertoire pour les rapports s'il n'existe pas
        reports_dir = "reports"
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)
        
        # Générer un nom de fichier avec la date et l'heure actuelles
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(reports_dir, f"network_usage_report_{timestamp}.png")
        
        # Sauvegarder le graphique
        plt.savefig(report_file, dpi=150)
        plt.close()
        
        return report_file
        
    except Exception as e:
        print(f"{Fore.RED}Erreur lors de la création du graphique réseau: {str(e)}")
        return None

def send_network_report():
    """Génère et envoie un rapport réseau sur Discord avec plusieurs embeds thématiques."""
    try:
        print(f"{Fore.CYAN}Génération du rapport réseau...")
        
        # Créer le graphique réseau
        graph_file = create_network_graph()
        if not graph_file:
            print(f"{Fore.RED}Impossible de générer le graphique réseau.")
            return
        
        # Récupérer les informations réseau
        net_info = get_network_info()
        
        # Récupérer les informations système de base
        sys_info = get_system_info()
        
        # Créer le webhook pour les rapports réseau
        webhook = DiscordWebhook(url=DISCORD_NETWORK_WEBHOOK_URL, 
                                username="MCP Network AI")
        
        # Ajouter l'image du graphique
        with open(graph_file, "rb") as f:
            webhook.add_file(file=f.read(), filename=os.path.basename(graph_file))
        
        # --------- EMBED 1: TITRE ET INFOS GÉNÉRALES ---------
        embed_title = DiscordEmbed(
            title=f"🌐 Rapport Réseau MCP AI Monitor - {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            description=f"Analyse détaillée de l'activité réseau sur **{sys_info['hostname']}**.",
            color=0x3498db  # Bleu
        )
        
        embed_title.set_timestamp()
        embed_title.set_footer(text=f"MCP AI Monitor | OS: {sys_info['os']}")
        
        # --------- EMBED 2: GRAPHIQUE RÉSEAU ---------
        embed_graph = DiscordEmbed(
            title=f"📈 Graphique d'Utilisation Réseau",
            color=0x9b59b6  # Violet
        )
        
        embed_graph.set_image(url=f"attachment://{os.path.basename(graph_file)}")
        
        # Ajouter les débits dans la description
        embed_graph.add_embed_field(
            name="📊 Activité Actuelle",
            value=f"**Débit montant:** {net_info['upload_speed']:.2f} KB/s\n"
                 f"**Débit descendant:** {net_info['download_speed']:.2f} KB/s\n"
                 f"**Total envoyé:** {net_info['total_sent']:.2f} GB\n"
                 f"**Total reçu:** {net_info['total_recv']:.2f} GB"
        )
        
        embed_graph.set_footer(text="MCP AI Monitor | Graphique réseau")
        
        # --------- EMBED 3: INTERFACES RÉSEAU ---------
        embed_interfaces = DiscordEmbed(
            title=f"🖧 Interfaces Réseau",
            color=0x1abc9c  # Turquoise
        )
        
        # Tableau formaté des interfaces
        interfaces_info = ""
        for i, interface in enumerate(net_info['interfaces']):
            interfaces_info += f"**Interface {i+1}:** `{interface['name']}`\n"
            interfaces_info += f"   └─ IP: {interface['ip']}, Masque: {interface['netmask']}\n"
        
        embed_interfaces.description = interfaces_info if interfaces_info else "Aucune interface réseau active."
        embed_interfaces.set_footer(text="MCP AI Monitor | Interfaces réseau")
        
        # --------- EMBED 4: CONNEXIONS ACTIVES ---------
        if net_info['connections']:
            embed_connections = DiscordEmbed(
                title=f"🔌 Connexions Réseau Actives",
                color=0xf39c12  # Orange
            )
            
            # Tableau formaté des connexions
            connections_info = ""
            for i, conn in enumerate(net_info['connections']):
                try:
                    process_name = psutil.Process(conn['pid']).name() if conn['pid'] else "Inconnu"
                except:
                    process_name = "Inconnu"
                    
                connections_info += f"**{i+1}.** `{process_name}` (PID: {conn['pid']})\n"
                connections_info += f"   └─ {conn['local_addr']} → {conn['remote_addr']}\n"
            
            embed_connections.description = connections_info
            embed_connections.set_footer(text="MCP AI Monitor | Connexions actives")
            
            # Ajouter cet embed uniquement s'il y a des connexions
            webhook.add_embed(embed_connections)
        
        # Ajouter les embeds principaux au webhook
        webhook.add_embed(embed_title)
        webhook.add_embed(embed_graph)
        webhook.add_embed(embed_interfaces)
        
        # Envoyer le webhook
        response = webhook.execute()
        
        if response.status_code >= 200 and response.status_code < 300:
            print(f"{Fore.GREEN}Rapport réseau envoyé avec succès sur Discord !")
        else:
            print(f"{Fore.RED}Erreur lors de l'envoi sur Discord: Code {response.status_code}")
        
    except Exception as e:
        print(f"{Fore.RED}Erreur lors de l'envoi du rapport réseau: {str(e)}")

def view_statistics(share_on_discord=False):
    """Affiche les statistiques collectées sous forme de graphiques."""
    data_file = os.path.join("data", "data.csv")
    
    if not os.path.exists(data_file):
        print(f"{Fore.RED}Erreur: Le fichier de données {data_file} n'existe pas.")
        print(f"{Fore.YELLOW}Exécutez d'abord 'python mcp.py collect' pour collecter des données.")
        return
    
    print(f"{Fore.CYAN}Chargement des données et génération des graphiques...")
    
    try:
        # Utiliser un style moderne
        plt.style.use('ggplot')
        
        # Définir une palette de couleurs attrayante
        colors = ['#2C82C9', '#EF4836', '#27ae60', '#8E44AD', '#F89406']
        
        # Charger les données
        df = pd.read_csv(data_file)
        
        if len(df) < 2:
            print(f"{Fore.RED}Pas assez de données pour générer des graphiques.")
            return
        
        # Convertir les timestamps en dates
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Créer un graphique avec deux sous-plots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        # Graphique d'utilisation CPU
        ax1.plot(df['timestamp'], df['cpu_percent'], color=colors[0], linewidth=2, label='CPU %')
        ax1.set_title('Utilisation CPU au fil du temps', fontsize=16, fontweight='bold')
        ax1.set_ylabel('Utilisation CPU (%)', fontsize=12)
        ax1.set_xlabel('Heure', fontsize=12)
        # Ajouter une ligne horizontale pour la moyenne
        cpu_mean = df['cpu_percent'].mean()
        ax1.axhline(y=cpu_mean, color=colors[2], linestyle='--', alpha=0.7, 
                    label=f'Moyenne: {cpu_mean:.2f}%')
        # Ajouter des annotations pour les points maximums
        cpu_max_idx = df['cpu_percent'].idxmax()
        cpu_max = df['cpu_percent'].max()
        ax1.scatter(df['timestamp'][cpu_max_idx], cpu_max, color=colors[1], s=100, zorder=5)
        ax1.annotate(f'Max: {cpu_max:.2f}%', 
                    xy=(df['timestamp'][cpu_max_idx], cpu_max),
                    xytext=(10, 10), textcoords='offset points',
                    arrowprops=dict(arrowstyle='->', color=colors[1]))
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='upper right')
        
        # Graphique d'utilisation RAM
        ax2.plot(df['timestamp'], df['ram_percent'], color=colors[1], linewidth=2, label='RAM %')
        ax2.set_title('Utilisation RAM au fil du temps', fontsize=16, fontweight='bold')
        ax2.set_ylabel('Utilisation RAM (%)', fontsize=12)
        ax2.set_xlabel('Heure', fontsize=12)
        # Ajouter une ligne horizontale pour la moyenne
        ram_mean = df['ram_percent'].mean()
        ax2.axhline(y=ram_mean, color=colors[2], linestyle='--', alpha=0.7, 
                    label=f'Moyenne: {ram_mean:.2f}%')
        # Ajouter des annotations pour les points maximums
        ram_max_idx = df['ram_percent'].idxmax()
        ram_max = df['ram_percent'].max()
        ax2.scatter(df['timestamp'][ram_max_idx], ram_max, color=colors[0], s=100, zorder=5)
        ax2.annotate(f'Max: {ram_max:.2f}%', 
                    xy=(df['timestamp'][ram_max_idx], ram_max),
                    xytext=(10, 10), textcoords='offset points',
                    arrowprops=dict(arrowstyle='->', color=colors[0]))
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc='upper right')
        
        # Ajouter un titre global
        fig.suptitle('MCP AI Monitor - Rapport d\'utilisation Système', 
                    fontsize=20, fontweight='bold', y=0.98)
        
        # Ajouter des informations sur le rapport
        plt.figtext(0.5, 0.01, f'Rapport généré le {datetime.now().strftime("%d/%m/%Y à %H:%M:%S")}',
                   ha='center', fontsize=10, style='italic')
        
        # Ajuster le layout
        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        
        # Créer le répertoire pour les rapports s'il n'existe pas
        reports_dir = "reports"
        if not os.path.exists(reports_dir):
            os.makedirs(reports_dir)
        
        # Générer un nom de fichier avec la date et l'heure actuelles
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(reports_dir, f"system_usage_report_{timestamp}.png")
        
        # Sauvegarder le graphique
        plt.savefig(report_file, dpi=150)
        
        # Calculer les statistiques supplémentaires
        stats = df[['cpu_percent', 'ram_percent']].describe()
        stats_data = {
            "cpu_percent": {
                "mean": stats['cpu_percent']['mean'],
                "std": stats['cpu_percent']['std'],
                "min": stats['cpu_percent']['min'],
                "max": stats['cpu_percent']['max']
            },
            "ram_percent": {
                "mean": stats['ram_percent']['mean'],
                "std": stats['ram_percent']['std'],
                "min": stats['ram_percent']['min'],
                "max": stats['ram_percent']['max']
            },
            "count": len(df)
        }
        
        # Afficher des statistiques supplémentaires
        print(f"\n{Fore.GREEN}Statistiques d'utilisation système:")
        print(f"{Fore.YELLOW}{stats}")
        
        print(f"\n{Fore.GREEN}Graphique sauvegardé dans: {Fore.CYAN}{report_file}")
        print(f"{Fore.YELLOW}Ouvrez ce fichier pour visualiser les tendances d'utilisation système.")
        
        # Partager sur Discord si demandé
        if share_on_discord:
            send_discord_report(report_file, stats_data)
        
        # Afficher le graphique (uniquement si l'environnement le permet)
        plt.show()
        
        return report_file, stats_data
        
    except Exception as e:
        print(f"{Fore.RED}Erreur lors de la génération des statistiques: {str(e)}")
        return None, None

def parse_arguments():
    """Parse les arguments de ligne de commande."""
    parser = argparse.ArgumentParser(description="MCP_AI_Monitor - Surveillance système avec IA")
    
    parser.add_argument("action", choices=["collect", "train", "monitor", "all", "stats", "discord", "network"], 
                        help="Action à exécuter")
    
    parser.add_argument("--duration", type=int, default=60,
                        help="Durée de la collecte de données en secondes (pour l'action 'all')")
    
    parser.add_argument("--report", action="store_true",
                        help="Envoyer un rapport à Discord après l'exécution (pour l'action 'all')")
    
    return parser.parse_args()

def main():
    """Fonction principale du programme."""
    print_banner()
    
    if not check_dependencies():
        return
    
    args = parse_arguments()
    
    if args.action == "collect":
        print(f"{Fore.CYAN}Lancement de la collecte de données...")
        run_module("collect_data")
        
    elif args.action == "train":
        print(f"{Fore.CYAN}Lancement de l'entraînement du modèle...")
        run_module("train_model")
        
    elif args.action == "monitor":
        print(f"{Fore.CYAN}Lancement de la surveillance en temps réel...")
        run_module("monitor_ai")
        
    elif args.action == "stats":
        print(f"{Fore.CYAN}Génération des statistiques et graphiques...")
        view_statistics(share_on_discord=False)
        
    elif args.action == "discord":
        print(f"{Fore.CYAN}Génération et partage du rapport sur Discord...")
        view_statistics(share_on_discord=True)
        
    elif args.action == "network":
        print(f"{Fore.CYAN}Analyse du réseau et envoi du rapport sur Discord...")
        send_network_report()
        
    elif args.action == "all":
        print(f"{Fore.CYAN}Exécution de la séquence complète...")
        print(f"\n{Fore.YELLOW}1. Collecte des données (pendant {args.duration} secondes)...")
        # Exécuter la collecte pendant une durée limitée
        try:
            subprocess.run([sys.executable, "collect_data.py"], timeout=args.duration)
        except subprocess.TimeoutExpired:
            print(f"{Fore.GREEN}Collecte de données terminée après {args.duration} secondes.")
        
        print(f"\n{Fore.YELLOW}2. Entraînement du modèle...")
        run_module("train_model")
        
        # Si l'option --report est activée, générer et envoyer un rapport
        if args.report:
            print(f"\n{Fore.YELLOW}Génération et envoi du rapport sur Discord...")
            report_file, stats_data = view_statistics(share_on_discord=False)
            if report_file and stats_data:
                send_discord_report(report_file, stats_data)
                
            print(f"\n{Fore.YELLOW}Analyse du réseau et envoi du rapport sur Discord...")
            send_network_report()
        
        print(f"\n{Fore.YELLOW}3. Lancement de la surveillance...")
        run_module("monitor_ai")

if __name__ == "__main__":
    main() 