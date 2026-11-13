"""Draw the figures from the result tables.

    python experiments/make_figures.py      (after run_all.py; needs matplotlib)

Writes PNG and PDF files to experiments/figures/. Figures are drawn only from the CSV
files in experiments/results/, never from numbers typed into this script.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from common import FIGURES, RESULTS, read_csv

plt.rcParams.update({"font.size": 8, "font.family": "serif", "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#dddddd", "grid.linewidth": 0.5, "legend.frameon": False,
                     "pdf.fonttype": 42, "savefig.bbox": "tight", "savefig.pad_inches": 0.02})
STYLE = {   # distinguishable in greyscale: line style and marker, not colour alone
    "ClinGuard 0.1.3": dict(color="black", ls="-", marker="s", lw=1.6),
    "Edit-distance ratio": dict(color="#555555", ls="--", marker="o", mfc="white"),
    "Partial ratio": dict(color="#555555", ls=":", marker="^", mfc="white", lw=1.4),
    "ClinGuard 0.1.1": dict(color="#888888", ls="-.", marker="x"),
    "Token-set ratio": dict(color="#aaaaaa", ls="-", marker="d", mfc="white"),
}
FIGURES.mkdir(exist_ok=True)


def save(fig, name):
    for ext in ("png", "pdf"):
        fig.savefig(FIGURES / f"{name}.{ext}", dpi=300, metadata={"CreationDate": None} if ext == "pdf" else None)
    plt.close(fig)
    print("wrote", name)


# Fig. 1: T3 embedded-phrase recall
rows = read_csv(RESULTS / "table4_t3_embedded_phrases.csv")
fig, ax = plt.subplots(figsize=(3.45, 2.2))
for name in ("ClinGuard 0.1.3", "Edit-distance ratio", "Partial ratio", "ClinGuard 0.1.1", "Token-set ratio"):
    r = [x for x in rows if x["scorer"] == name]
    ax.plot([int(x["extra_words"]) for x in r], [float(x["correct_pct"]) for x in r], ms=3.5, label=name, **{"lw": 1.0, **STYLE[name]})
ax.set(xlabel="Extra words around the lexicon phrase", ylabel="Correct match (%)", ylim=(35, 103), xticks=[0, 1, 2, 3, 4, 6, 8])
ax.legend(loc="lower left", fontsize=6.5, handlelength=3)
save(fig, "fig_t3_embedded_phrases")

# Fig. 2: T1 wrong-term matches by scorer
rows = read_csv(RESULTS / "table1_t1_t2_scorers.csv")
fig, ax = plt.subplots(figsize=(3.45, 1.9))
names = [r["scorer"] for r in rows]
vals = [int(r["t1_wrong_term"]) for r in rows]
bars = ax.barh(names[::-1], vals[::-1], color=["black" if n == "ClinGuard 0.1.3" else "#999999" for n in names[::-1]], height=0.6)
ax.bar_label(bars, padding=2, fontsize=7)
ax.set(xlabel="Wrong-term matches on 60 held-out phrases (lower is better)", xlim=(0, 40))
ax.grid(axis="y", visible=False)
save(fig, "fig_t1_wrong_term_matches")

# Fig. 3: threshold sweep
rows = read_csv(RESULTS / "table3_threshold_sweep.csv")
fig, ax = plt.subplots(figsize=(3.45, 2.0))
for name in ("ClinGuard 0.1.3", "ClinGuard 0.1.1"):
    r = [x for x in rows if x["scorer"] == name]
    ax.plot([float(x["threshold"]) for x in r], [int(x["t1_wrong_term"]) for x in r], ms=3.5, label=name, **{"lw": 1.0, **STYLE[name]})
ax.axvline(0.75, color="#bbbbbb", lw=0.8, ls=":")
ax.text(0.745, 44, "default", fontsize=6.5, color="#666666", ha="right")
ax.set(xlabel="Match threshold", ylabel="Wrong-term matches (of 60)", ylim=(-2, 60))
ax.legend(fontsize=6.5)
save(fig, "fig_threshold_sweep")

# Fig. 4: danger rules by path
rows = read_csv(RESULTS / "table5_t4_danger_rules.csv")
fig, ax = plt.subplots(figsize=(3.45, 1.7))
labels = [r["condition"] for r in rows][::-1]
tp = [int(r["flagged_tp"]) for r in rows][::-1]
fn = [int(r["missed_fn"]) for r in rows][::-1]
b1 = ax.barh(labels, tp, color="black", height=0.55, label="Flagged")
b2 = ax.barh(labels, fn, left=tp, color="white", edgecolor="black", hatch="///", height=0.55, label="Missed")
ax.bar_label(b1, label_type="center", color="white", fontsize=7)
ax.bar_label(b2, labels=[str(v) if v else "" for v in fn], label_type="center", fontsize=7,
             bbox=dict(facecolor="white", edgecolor="none", pad=1))
ax.set(xlabel="Danger-marked phrases (of 30)", xlim=(0, 30))
ax.grid(axis="y", visible=False)
ax.legend(fontsize=6.5, ncol=2, loc="lower center", bbox_to_anchor=(0.5, 1.0))
save(fig, "fig_t4_danger_rules")


# Fig. 5: recall on known phrases against false matches on unknown phrases (T6)
rows = read_csv(RESULTS / "table7_risk_coverage.csv")
fig, axes = plt.subplots(1, 2, figsize=(3.45, 2.35), sharey=True)
for ax, case_set, title in zip(axes, ("noisy", "clean"), ("(a) Spelling noise + extra words", "(b) Extra words only")):
    for name in ("ClinGuard 0.1.3", "Edit-distance ratio", "Partial ratio", "Token-set ratio", "ClinGuard 0.1.1"):
        r = [x for x in rows if x["case_set"] == case_set and x["scorer"] == name]
        ax.plot([float(x["unknown_false_match_pct"]) for x in r], [float(x["known_recall_pct"]) for x in r],
                ms=2.2, label=name, **{"lw": 0.9, **STYLE[name]})
    d = [x for x in rows if x["case_set"] == case_set and x["scorer"] == "ClinGuard 0.1.3" and x["threshold"] == "0.750"][0]
    ax.plot(float(d["unknown_false_match_pct"]), float(d["known_recall_pct"]), "o", ms=6, mfc="none", mec="black", mew=0.8)
    ax.set_xscale("symlog", linthresh=1)
    ax.set_xlim(0, 100)
    ax.set_xticks([0, 1, 3, 10, 100]); ax.set_xticklabels(["0", "1", "3", "10", "100"], fontsize=6.5)
    ax.set_ylim(60, 101)
    ax.set_title(title, fontsize=6.5, pad=3)
axes[0].set_ylabel("Recall on known phrases (%)", fontsize=7)
fig.supxlabel("False matches on unknown phrases (%, log scale above 1)", fontsize=7, y=-0.04)
h, l = axes[0].get_legend_handles_labels()
fig.legend(h, l, loc="upper center", ncol=3, fontsize=5.6, handlelength=2.6, bbox_to_anchor=(0.53, 1.07), columnspacing=1.0)
save(fig, "fig_t6_recall_vs_false_match")
