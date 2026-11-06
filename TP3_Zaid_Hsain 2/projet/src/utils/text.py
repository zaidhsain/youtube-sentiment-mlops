"""Nettoyage de texte partagé par l'entraînement ET l'API.

Module volontairement sans pandas/sklearn : il est embarqué dans l'image Docker.
Utiliser la même fonction des deux côtés évite le « training/serving skew ».
"""
import re

try:
    import emoji
except ImportError:  # l'API peut tourner sans le paquet emoji (emojis alors supprimés)
    emoji = None

URL_RE = re.compile(r"https?://\S+|www\.\S+")
MENTION_RE = re.compile(r"@[\w.-]+")
HASHTAG_RE = re.compile(r"#(\w+)")
HTML_RE = re.compile(r"<[^>]+>")
NON_ALPHA_RE = re.compile(r"[^a-z\s]")
REPEAT_RE = re.compile(r"(.)\1{2,}")  # "soooo" -> "soo"
SPACES_RE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """Nettoie un commentaire brut (Reddit ou YouTube)."""
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = HTML_RE.sub(" ", text)
    text = URL_RE.sub(" ", text)
    text = MENTION_RE.sub(" ", text)
    text = HASHTAG_RE.sub(r"\1", text)          # garde le mot du hashtag
    if emoji is not None:                       # 😍 -> " smiling face with heart eyes "
        text = emoji.demojize(text, delimiters=(" ", " "))
        text = text.replace("_", " ")
    text = text.replace("'", "").replace("’", "")  # don't -> dont
    text = NON_ALPHA_RE.sub(" ", text)          # chiffres, ponctuation, symboles
    text = REPEAT_RE.sub(r"\1\1", text)
    return SPACES_RE.sub(" ", text).strip()
