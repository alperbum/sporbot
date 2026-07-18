import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    "tc_kimlik": "40105524674",
    "sifre": "dsj2yyjw1",
    "telegram_token": "8767976833:AAEZThBoMPWL8EHzaQiYu2iU9ErlAKck1BM",
    "telegram_chat_id": "1585282829",
    "tarama_araligi_dakika": 2,
    "secili_spor": "TENİS",
    "tercih_edilen_gunler": [],
    "tercih_edilen_saatler": [],
    "test_modu": False,
    "yeni_seans_yukseltme_izni": False,
    "alarm_dakika_once": 30,
    "aktif_alarmlar": []
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
            # Merge with defaults in case of new keys
            merged = {**DEFAULT_CONFIG, **config}
            return merged
    except Exception as e:
        print(f"Error loading config: {e}")
        return DEFAULT_CONFIG

def save_config(config):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving config: {e}")
