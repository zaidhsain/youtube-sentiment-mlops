"""Style graphique commun aux figures du projet (même charte que le rapport)."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

INK = "#1f1b16"
BURGUNDY = "#7b1e2b"
COLORS = {-1: "#8c2f39", 0: "#a39e93", 1: "#4a6b55"}   # négatif, neutre, positif
NAMES = {-1: "Négatif", 0: "Neutre", 1: "Positif"}
CMAP = LinearSegmentedColormap.from_list("bordeaux", ["#fbf8f3", "#d9b3b0", BURGUNDY])


def apply():
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
        "font.size": 10.5,
        "axes.edgecolor": INK,
        "axes.labelcolor": INK,
        "axes.titlesize": 11.5,
        "axes.titleweight": "normal",
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": INK,
        "ytick.color": INK,
        "text.color": INK,
        "figure.facecolor": "white",
        "savefig.bbox": "tight",
        "savefig.dpi": 160,
        "legend.frameon": False,
    })
