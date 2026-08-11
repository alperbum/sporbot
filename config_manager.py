import json
import os
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

CONFIG_LOCK = threading.Lock()

DEFAULT_CONFIG = {
    "tc_kimlik": "",
    "sifre": "",
    "telegram_token": "",
    "telegram_chat_id": "",
    "tarama_araligi_saniye": 20,
    "secili_spor": "TENİS",
    "tercih_edilen_gunler": [],
    "tercih_edilen_saatler": [],
    "test_modu": False,
    "yeni_seans_yukseltme_izni": False,
    "alarm_dakika_once": 30,
    "aktif_alarmlar": [],
    "kort_3_izni": True,
    "kort_4_izni": True,
    "kort_6_izni": True,
    "kort_1_izni": True,
    "kort1_kort3_sarti": False,
}

# Config içerebileceği beklenen tüm anahtarlar (eksik olanlar default ile doldurulur)
KNOWN_KEYS = set(DEFAULT_CONFIG.keys())


def _merge_defaults(stored: dict) -> dict:
    """Saklanmış config'i default'larla birleştirir; eksik anahtarları tamamlar."""
    merged = dict(DEFAULT_CONFIG)
    if isinstance(stored, dict):
        merged.update(stored)
    # Bilinmeyen anahtarları da korusun (ileriye dönük uyumluluk)
    return merged


def _coerce_types(cfg: dict) -> dict:
    """Yanlış tip verileri güvenli şekilde dönüştürür. Hatalıysa default kullanılır."""
    try:
        v = cfg.get("tarama_araligi_saniye")
        if v is None or v == "":
            cfg["tarama_araligi_saniye"] = DEFAULT_CONFIG["tarama_araligi_saniye"]
        else:
            n = int(v)
            if n < 3:
                n = 3
            cfg["tarama_araligi_saniye"] = n
    except (ValueError, TypeError):
        # Eski "tarama_araligi_dakika" alanından yedek dene
        try:
            cfg["tarama_araligi_saniye"] = max(3, int(cfg.get("tarama_araligi_dakika", 2)) * 60)
        except (ValueError, TypeError):
            cfg["tarama_araligi_saniye"] = DEFAULT_CONFIG["tarama_araligi_saniye"]

    try:
        cfg["alarm_dakika_once"] = max(0, int(cfg.get("alarm_dakika_once", 30)))
    except (ValueError, TypeError):
        cfg["alarm_dakika_once"] = DEFAULT_CONFIG["alarm_dakika_once"]

    for k in ("test_modu", "yeni_seans_yukseltme_izni",
              "kort_3_izni", "kort_4_izni", "kort_6_izni", "kort_1_izni", "kort1_kort3_sarti"):
        if not isinstance(cfg.get(k), bool):
            cfg[k] = DEFAULT_CONFIG[k]

    if not isinstance(cfg.get("secili_spor"), str) or not cfg.get("secili_spor"):
        cfg["secili_spor"] = DEFAULT_CONFIG["secili_spor"]

    for k in ("tercih_edilen_gunler", "tercih_edilen_saatler", "aktif_alarmlar"):
        if not isinstance(cfg.get(k), list):
            cfg[k] = []

    for k in ("tc_kimlik", "sifre", "telegram_token", "telegram_chat_id"):
        if not isinstance(cfg.get(k), str):
            cfg[k] = ""

    return cfg


def load_config() -> dict:
    """config.json'ı güvenle yükler. Hata olursa default'larla devam eder."""
    if not os.path.exists(CONFIG_FILE):
        # İlk açılışta örnek dosya oluşturulur, ancak boş placeholder'larla
        save_config(DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            stored = json.load(f)
        return _coerce_types(_merge_defaults(stored))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Config yüklenirken hata: {e}. Varsayılanlar kullanılıyor.")
        # Bozuk config.json'ı overwrite et ki sonraki açılışta yazılabilsin
        try:
            save_config(DEFAULT_CONFIG)
        except Exception:
            pass
        return dict(DEFAULT_CONFIG)


def save_config(config: dict):
    """config.json'a thread-safe ve atomik şekilde yazar."""
    if not isinstance(config, dict):
        return
    with CONFIG_LOCK:
        # Yazım için temiz bir config hazırla (eksik anahtarları default'la)
        cfg = _coerce_types(dict(DEFAULT_CONFIG, **config))
        try:
            tmp_path = CONFIG_FILE + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
            # Windows'ta hedef dosya varsa üzerine yaz, yoksa taşı
            if os.name == "nt":
                os.replace(tmp_path, CONFIG_FILE)
            else:
                os.replace(tmp_path, CONFIG_FILE) if os.path.exists(CONFIG_FILE) else os.rename(tmp_path, CONFIG_FILE)
        except Exception as e:
            print(f"Config kaydedilirken hata: {e}")
