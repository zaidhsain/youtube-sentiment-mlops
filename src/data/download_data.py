"""Phase 2.1 : Téléchargement du dataset Reddit labelisé.

Usage : python -m src.data.download_data
"""
from pathlib import Path

import pandas as pd
import requests

from src.utils.logger import get_logger

DATA_URL = (
    "https://raw.githubusercontent.com/Himanshu-1703/"
    "reddit-sentiment-analysis/refs/heads/main/data/reddit.csv"
)
RAW_PATH = Path("data/raw/reddit.csv")
LABELS = {-1: "négatif", 0: "neutre", 1: "positif"}

logger = get_logger("download")


def download(url: str = DATA_URL, dest: Path = RAW_PATH) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Téléchargement depuis %s", url)
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    logger.info("Sauvegardé dans %s (%.1f Ko)", dest, len(resp.content) / 1024)
    return dest


def print_stats(path: Path = RAW_PATH) -> pd.DataFrame:
    df = pd.read_csv(path)
    print(f"\nColonnes          : {list(df.columns)}")
    print(f"Nombre de lignes  : {len(df)}")
    print(f"Valeurs manquantes:\n{df.isna().sum()}\n")
    label_col = "category" if "category" in df.columns else "label"
    counts = df[label_col].value_counts().sort_index()
    print("Distribution des labels :")
    for lab, n in counts.items():
        print(f"  {int(lab):>2} ({LABELS.get(int(lab), '?'):8}) : {n:6d}  ({n / len(df):.1%})")
    return df


if __name__ == "__main__":
    print_stats(download())
