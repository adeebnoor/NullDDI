"""NullDDI step 20 v1.0: manuscript figures (PNAS sizes: 1 column 8.7 cm, 2 columns 17.8 cm). Numbers are read
from the run reports v7, v9, v12a_v2, v13, v15, v16, v17 (typed here once, each with its source)."""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
INK, INK2, GREY, LGREY, ACC, GRID = "#0b0b0b", "#52514e", "#9a9893", "#d9d7d2", "#2a78d6", "#e8e6e1"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 7, "axes.edgecolor": GREY, "axes.labelcolor": INK2,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False})
CM = 1 / 2.54
def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(f"{name}.{ext}", dpi=600 if ext == "png" else None, bbox_inches="tight")

# ---------- Fig 1: pipeline and anatomy of a record
fig, ax = plt.subplots(figsize=(17.8 * CM, 6.2 * CM)); ax.set_xlim(0, 100); ax.set_ylim(0, 40); ax.axis("off")
steps = [("264,800", "US labels\n(openFDA)"), ("115,275", "candidates\nextractor A (rules)"), ("4 runs", "extractor B\n(language model)"),
         ("4,547", "sentences accepted\n(A and all B agree)"), ("1,032", "directional\nstatements: 955\npairs, 509 drugs")]
for i, (n, t) in enumerate(steps):
    x = 2 + i * 19.6
    ax.add_patch(FancyBboxPatch((x, 23), 16.5, 13, boxstyle="round,pad=0.3,rounding_size=1.2", fc="white", ec=ACC if i == 4 else GREY, lw=1.2 if i == 4 else 0.8))
    ax.text(x + 8.25, 32.3, n, ha="center", va="center", fontsize=9, fontweight="bold", color=ACC if i == 4 else INK)
    ax.text(x + 8.25, 26.2, t, ha="center", va="center", fontsize=6.0 if i == 4 else 6.3, color=INK2, linespacing=1.15)
    if i < 4:
        ax.annotate("", xy=(x + 19.3, 29.5), xytext=(x + 16.9, 29.5), arrowprops=dict(arrowstyle="-|>", color=GREY, lw=0.8))
ax.text(1, 38.7, "A  From labels to a reference (no human curation; provenance to the sentence)", fontsize=7.5, fontweight="bold", color=INK)
ax.text(1, 18.2, "B  One record carries four properties", fontsize=7.5, fontweight="bold", color=INK)
props = [("Direction", "rifampin → selpercatinib\n(reverse not documented)"), ("Dimension", "pharmacokinetics\n(exposure, not effect)"),
         ("Standard", "clinical relevance,\nnot equivalence"), ("Condition", "single dose of rifampin\n(repeated: AUC −87%)")]
for i, (h, t) in enumerate(props):
    x = 2 + i * 24.5
    ax.add_patch(FancyBboxPatch((x, 2), 22, 12.5, boxstyle="round,pad=0.3,rounding_size=1.2", fc="#f4f3f0", ec="none"))
    ax.text(x + 1.2, 11.4, h, fontsize=7, fontweight="bold", color=INK)
    ax.text(x + 1.2, 4.6, t, fontsize=6.3, color=INK2, va="bottom")
save(fig, "Fig1_pipeline"); plt.close(fig)

# ---------- Fig 2: directionality in three sources (v7, v9, v15)
rows = [("NullDDI, FDA labels\n(final reference, 955 pairs)", 14.2, 79.6, 6.2),
        ("FDA labels, rules only\n(1,160 pairs)", 12.5, 63.3, 24.2),
        ("EMA product information,\nrules only (329 pairs)", 17.9, 61.4, 20.7),
        ("PK-DDI DB, manual curation\n(Jang 2022; 2,290 pairs)", 23.4, 76.6, 0.0)]
fig, ax = plt.subplots(figsize=(11.4 * CM, 5.6 * CM))
for i, (lab, both, one, und) in enumerate(rows[::-1]):
    y = i
    ax.barh(y, both, color=GREY, height=0.62, edgecolor="white", lw=1.5)
    ax.barh(y, one, left=both, color=ACC, height=0.62, edgecolor="white", lw=1.5)
    ax.barh(y, und, left=both + one, color=LGREY, height=0.62, edgecolor="white", lw=1.5)
    ax.text(both / 2, y, f"{both:.0f}%", ha="center", va="center", color="white", fontsize=6.5)
    ax.text(both + one / 2, y, f"{one:.0f}%", ha="center", va="center", color="white", fontsize=7, fontweight="bold")
ax.set_yticks(range(4)); ax.set_yticklabels([r[0] for r in rows[::-1]], fontsize=6.5)
ax.set_xlim(0, 100); ax.set_xlabel("Share of documented non-interacting pairs (%)")
ax.xaxis.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)
ax.set_title("Most documented non-interactions cover one direction only", loc="left", fontsize=8, color=INK, pad=14)
for x, t, c in ((5, "both directions", GREY), (40, "one direction only", ACC), (90, "direction unresolved", INK2)):
    ax.text(x, 3.52, t, color=c, fontsize=6.3, ha="center", va="bottom", fontweight="bold" if c == ACC else None)
save(fig, "Fig2_directionality"); plt.close(fig)

# ---------- Fig 3: population exposure, NHANES (v12a_v2): estimate (millions) and SE
rows = [("Any pair with a generalizable\nnon-interaction", 15.1, 1.1, False),
        ("  documented in one direction", 12.3, 0.9, False),
        ("    other direction: no evidence\n    in labels or FDA tables", 10.9, 0.8, True),
        ("    other direction: ruled out\n    by FDA tables", 2.5, 0.4, False),
        ("  documented in both directions", 3.1, 0.5, False),
        ("Pair whose only statements\nare restricted", 3.6, 0.7, True)]
fig, ax = plt.subplots(figsize=(11.4 * CM, 6.6 * CM))
for i, (lab, est, se, hi) in enumerate(rows[::-1]):
    ax.barh(i, est, color=ACC if hi else GREY, height=0.6)
    ax.errorbar(est, i, xerr=1.96 * se, fmt="none", ecolor=INK2, elinewidth=0.8, capsize=2)
    ax.text(est + 1.96 * se + 0.3, i, f"{est:.1f} M", va="center", fontsize=6.5, color=INK, fontweight="bold" if hi else None)
ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows[::-1]], fontsize=6.3)
ax.set_xlabel("US residents using the pair (millions; 95% CI)"); ax.set_xlim(0, 19)
ax.xaxis.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)
ax.set_title("About 11 million US residents take a pair cleared in one direction only", loc="left", fontsize=8, color=INK)
ax.text(0, -1.85, "NHANES 2017–March 2020, prescription use in the past 30 days, both drugs from separate products; weighted to 322.3 million.", fontsize=5.6, color=INK2, transform=ax.transData)
save(fig, "Fig3_population"); plt.close(fig)

# ---------- Fig 4: models flatten the structure (v13, v17, v16)
fig, axs = plt.subplots(1, 3, figsize=(17.8 * CM, 6.6 * CM), gridspec_kw={"width_ratios": [1.05, 0.9, 1.15], "wspace": 1.05})
# A: LLM warnings N1 vs N2 (stable answers)
llm = [("Sonnet 5.5", 6.6, 1.1), ("Haiku 5.5", 10.6, 1.8), ("GPT-6.2 Sol", 5.1, 1.1), ("Gemini 4 Carbon", 5.5, 1.9)]
ax = axs[0]
for i, (m, n1, n2) in enumerate(llm[::-1]):
    ax.plot([n2, n1], [i, i], color=LGREY, lw=2, zorder=1)
    ax.scatter([n2], [i], color=GREY, s=22, zorder=2); ax.scatter([n1], [i], color=ACC, s=22, zorder=3)
ax.set_yticks(range(4)); ax.set_yticklabels([m for m, *_ in llm[::-1]], fontsize=6.3)
ax.set_xlim(0, 12); ax.set_ylim(-0.6, 3.9); ax.set_xlabel("Warned on a documented\nnon-interaction (%)")
ax.text(6.6, 3.35, "one direction", color=ACC, fontsize=5.8, ha="center"); ax.text(1.1, 3.35, "both", color=INK2, fontsize=5.8, ha="center")
ax.set_title("A  Language models", loc="left", fontsize=7, color=INK)
ax.xaxis.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)
# B: conditional statements: unqualified reassurance, Sonnet without vs with evidence (v13/v17)
ax = axs[1]
cats = ["None", "Sentence", "Record"]; allc = [77.3, 97.3, 97.3]; docd = [44.4, 77.8, 77.8]
xs = range(3)
ax.plot(xs, allc, color=GREY, marker="o", ms=4, lw=1.2); ax.plot(xs, docd, color=ACC, marker="o", ms=4, lw=1.2)
ax.set_xticks(list(xs)); ax.set_xticklabels(cats, fontsize=6); ax.set_ylim(0, 100)
ax.set_ylabel("\"No clinically significant\ninteraction\" (%)")
ax.text(1.55, 92, "all 150 restricted\nstatements", fontsize=5.4, color=INK2, ha="center", va="top")
ax.text(1.55, 74, "labels document an\ninteraction outside the\nrestriction (n = 18)", fontsize=5.4, color=ACC, ha="center", va="top")
ax.set_xlim(-0.3, 2.3); ax.yaxis.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)
ax.set_xlabel("Evidence given (Sonnet 5.5)"); ax.set_title("B  Restricted statements", loc="left", fontsize=7, color=INK)
# C: predictors: false alarms random vs documented + remedy (v16, v17)
ax = axs[2]
pred = [("Logistic regression", 36.9, 62.9, None), ("Gradient boosting", 29.0, 47.6, 33.2), ("DeepDDI-style MLP", 42.9, 64.7, None)]
for i, (m, r, d, fix) in enumerate(pred[::-1]):
    ax.plot([r, d], [i, i], color=LGREY, lw=2, zorder=1)
    ax.scatter([r], [i], color=GREY, s=22, zorder=2); ax.scatter([d], [i], color=ACC, s=22, zorder=3)
    if fix:
        ax.scatter([fix], [i], marker="D", color=INK, s=16, zorder=4)
        ax.annotate("with documented\nnegatives in training", xy=(fix, i), xytext=(fix + 14, i - 0.45), fontsize=5.3, color=INK, ha="center", va="top",
                    arrowprops=dict(arrowstyle="-", color=INK, lw=0.5))
ax.set_yticks(range(3)); ax.set_yticklabels([m for m, *_ in pred[::-1]], fontsize=6.3)
ax.set_xlim(20, 70); ax.set_ylim(-0.6, 2.9); ax.set_xlabel("False alarms at 90% sensitivity (%)")
ax.text(33, 2.45, "random\nnegatives", color=INK2, fontsize=5.6, ha="center"); ax.text(62, 2.45, "documented\nnegatives", color=ACC, fontsize=5.6, ha="center")
ax.set_title("C  Prediction models", loc="left", fontsize=7, color=INK)
ax.xaxis.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)
save(fig, "Fig4_models"); plt.close(fig)
print("ok")
