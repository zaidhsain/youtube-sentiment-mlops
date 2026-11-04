"""Phase 2.2 — Nettoyage, EDA, split train/test reproductible.

Usage : python -m src.data.preprocess
"""
from pathlib import Path

import pandas as pd

from src.utils.text import clean_text

RAW_PATH = Path("data/raw/reddit.csv")
PROCESSED_DIR = Path("data/processed")
FIG_DIR = Path("reports/figures")
RANDOM_STATE = 42
TEST_SIZE = 0.2


def load_and_clean(path: Path = RAW_PATH) -> pd.DataFrame:
    df = pd.read_csv(path).rename(columns={"clean_comment": "text", "category": "label"})
    n0 = len(df)
    df = df.dropna(subset=["text"])
    df["text"] = df["text"].map(clean_text)
    df = df[df["text"].str.len() > 0]
    df = df.drop_duplicates(subset=["text"])
    df["label"] = df["label"].astype(int)
    print(f"Nettoyage : {n0} -> {len(df)} lignes (NaN, vides et doublons retirés)")
    return df[["text", "label"]].reset_index(drop=True)


def eda(df: pd.DataFrame) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    names = {-1: "Négatif", 0: "Neutre", 1: "Positif"}
    colors = {-1: "#e5484d", 0: "#8b8d98", 1: "#30a46c"}
    df = df.assign(n_words=df["text"].str.split().str.len())

    counts = df["label"].value_counts().sort_index()
    print("\nDistribution des classes :\n", counts.rename(index=names).to_string())
    print("\nLongueur (mots) par classe :\n",
          df.groupby("label")["n_words"].describe()[["mean", "50%", "max"]].rename(index=names).round(1))

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar([names[i] for i in counts.index], counts.values, color=[colors[i] for i in counts.index])
    ax.set_title("Distribution des classes")
    ax.set_ylabel("Nombre de commentaires")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "class_distribution.png", dpi=120)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4))
    for lab in (-1, 0, 1):
        ax.hist(df.loc[df.label == lab, "n_words"].clip(upper=150), bins=50,
                alpha=0.55, label=names[lab], color=colors[lab])
    ax.set_title("Longueur des commentaires (mots, tronquée à 150)")
    ax.set_xlabel("Nombre de mots")
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG_DIR / "text_length.png", dpi=120)
    plt.close(fig)


def split_and_save(df: pd.DataFrame) -> None:
    from sklearn.model_selection import train_test_split

    train, test = train_test_split(
        df, test_size=TEST_SIZE, stratify=df["label"], random_state=RANDOM_STATE
    )
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    train.to_csv(PROCESSED_DIR / "train.csv", index=False)
    test.to_csv(PROCESSED_DIR / "test.csv", index=False)
    print(f"\nSplit stratifié 80/20 (seed={RANDOM_STATE}) : train={len(train)}, test={len(test)}")


if __name__ == "__main__":
    data = load_and_clean()
    eda(data)
    split_and_save(data)
