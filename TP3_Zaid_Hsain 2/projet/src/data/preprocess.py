"""Phase 2.2 : Nettoyage, EDA, split train/test reproductible.

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
    import matplotlib.pyplot as plt

    from src.utils.plot_style import COLORS, NAMES, apply
    apply()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    df = df.assign(n_words=df["text"].str.split().str.len())

    counts = df["label"].value_counts().sort_index()
    print("\nDistribution des classes :\n", counts.rename(index=NAMES).to_string())
    print("\nLongueur (mots) par classe :\n",
          df.groupby("label")["n_words"].describe()[["mean", "50%", "max"]].rename(index=NAMES).round(1))

    # Répartition : barres horizontales annotées (effectif et part)
    fig, ax = plt.subplots(figsize=(6.2, 2.4))
    order = [1, 0, -1]
    ax.barh([NAMES[i] for i in order], [counts[i] for i in order],
            color=[COLORS[i] for i in order], height=0.55)
    for y, lab in enumerate(order):
        n = counts[lab]
        ax.text(n + 200, y, f"{n:,} ({n / len(df):.1%})".replace(",", " "), va="center", fontsize=9.5)
    ax.invert_yaxis()
    ax.set_xlim(0, counts.max() * 1.28)
    ax.set_xlabel("Nombre de commentaires")
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    fig.savefig(FIG_DIR / "class_distribution.png")
    plt.close(fig)

    # Longueur : histogrammes en contour, médiane en pointillés
    fig, ax = plt.subplots(figsize=(6.2, 3.0))
    for lab in (1, 0, -1):
        words = df.loc[df.label == lab, "n_words"].clip(upper=150)
        ax.hist(words, bins=60, histtype="step", linewidth=1.4, density=True,
                color=COLORS[lab], label=f"{NAMES[lab]} (médiane {int(words.median())} mots)")
        ax.axvline(words.median(), color=COLORS[lab], linestyle=":", linewidth=1)
    ax.set_xlabel("Nombre de mots (tronqué à 150)")
    ax.set_ylabel("Densité")
    ax.legend(fontsize=9)
    fig.savefig(FIG_DIR / "text_length.png")
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
