"""Draw the generic PFD / data-flow figure (no plant values). Run: python -m src.make_pfd [--out PATH]."""
import argparse
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


def box(ax, x, y, w, h, text, fc="#eef3f8", ec="#35506b"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02", fc=fc, ec=ec, lw=1.3))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=8)


def arrow(ax, p, q, color="#35506b", style="-|>", ls="-"):
    ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle=style, color=color, lw=1.3, ls=ls))


def main(out):
    fig, ax = plt.subplots(figsize=(13, 7.5))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 7.5)
    ax.axis("off")
    ax.set_title("Heater C (synthetic) - generic PFD and data flow. No plant values.", fontsize=11)

    # gas / fuel side
    ax.text(0.2, 6.9, "GAS / FUEL SIDE", fontsize=9, weight="bold", color="#8a3b12")
    gas = "#fbeee6"
    box(ax, 0.2, 5.6, 1.7, 0.8, "Fuel lot\n(PKS storage)", gas, "#8a3b12")
    box(ax, 2.4, 5.6, 1.5, 0.8, "Feeders", gas, "#8a3b12")
    box(ax, 4.4, 5.3, 2.2, 1.4, "Travelling-grate\nfurnace", gas, "#8a3b12")
    box(ax, 7.1, 5.6, 1.8, 0.8, "Economizer /\nair preheater", gas, "#8a3b12")
    box(ax, 9.4, 5.6, 1.5, 0.8, "Dust\ncollection", gas, "#8a3b12")
    box(ax, 11.3, 5.6, 1.4, 0.8, "ID fan\nand stack", gas, "#8a3b12")
    box(ax, 4.4, 4.2, 2.2, 0.6, "FD fan (air)", gas, "#8a3b12")
    box(ax, 7.1, 4.6, 1.8, 0.5, "Ash removal", gas, "#8a3b12")
    for p, q in [((1.9, 6.0), (2.4, 6.0)), ((3.9, 6.0), (4.4, 6.0)), ((6.6, 6.0), (7.1, 6.0)),
                 ((8.9, 6.0), (9.4, 6.0)), ((10.9, 6.0), (11.3, 6.0)), ((5.5, 4.8), (5.5, 5.3)),
                 ((6.6, 5.5), (7.1, 4.9))]:
        arrow(ax, p, q, "#8a3b12")

    # HTF side (separate loop)
    ax.text(0.2, 3.5, "HTF SIDE (separate closed loop)", fontsize=9, weight="bold", color="#1b5e3a")
    htf = "#e8f4ec"
    box(ax, 4.4, 2.3, 2.2, 0.9, "Heater coil\n(in furnace)", htf, "#1b5e3a")
    box(ax, 7.6, 2.3, 1.6, 0.9, "HTF supply\nheader", htf, "#1b5e3a")
    box(ax, 9.9, 2.3, 2.2, 0.9, "PET process\nusers (load)", htf, "#1b5e3a")
    box(ax, 1.0, 2.3, 1.8, 0.9, "HTF pump and\nexpansion tank", htf, "#1b5e3a")
    arrow(ax, (6.6, 2.75), (7.6, 2.75), "#1b5e3a")
    arrow(ax, (9.2, 2.75), (9.9, 2.75), "#1b5e3a")
    ax.plot([11.0, 11.0, 1.9, 1.9], [2.3, 1.7, 1.7, 2.3], color="#1b5e3a", lw=1.3)  # return line
    arrow(ax, (2.8, 2.75), (4.4, 2.75), "#1b5e3a")
    arrow(ax, (1.9, 1.7), (1.9, 2.3), "#1b5e3a")
    ax.text(6.4, 1.5, "return", fontsize=8, color="#1b5e3a")
    ax.plot([8.4, 8.4, 5.5, 5.5], [3.2, 3.55, 3.55, 3.2], color="#1b5e3a", lw=1.3, ls="--")
    ax.text(6.0, 3.62, "bypass (verify on site)", fontsize=8, color="#1b5e3a")

    # data flow
    ax.text(0.2, 1.1, "DATA FLOW (read-only, offline)", fontsize=9, weight="bold", color="#35506b")
    d = "#eef3f8"
    labels = ["Historian export\n(synthetic Level 1)", "Clean and\neligibility gate", "Forecast and\nrank options",
              "Guardrail\nre-check", "Operator log\n(accept/reject)"]
    xs = [0.2, 2.8, 5.4, 8.0, 10.6]
    for x, t in zip(xs, labels):
        box(ax, x, 0.2, 2.1, 0.7, t, d)
    for x in xs[:-1]:
        arrow(ax, (x + 2.1, 0.55), (x + 2.6, 0.55))
    ax.text(6.5, 0.0, "BMS/SIS/DCS remain sole control authorities - no write path from this tool",
            ha="center", fontsize=8, color="#a01919", weight="bold")
    fig.savefig(out, dpi=150, bbox_inches="tight")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="reports/05_PFD_and_dataflow.png")
    main(ap.parse_args().out)
