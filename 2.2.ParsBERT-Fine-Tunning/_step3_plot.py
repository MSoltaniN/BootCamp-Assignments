import os, sys, json
PKGS = r"C:\Users\pc\source\repos\AI\BootCamp Assignments\2.2.ParsBERT-Fine-Tunning\.pkgs"
sys.path.insert(0, PKGS)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = r"C:\Users\pc\source\repos\AI\BootCamp Assignments\2.2.ParsBERT-Fine-Tunning"
RUN = os.path.join(ROOT, "run")
S = json.load(open(os.path.join(RUN, "summary.json"), encoding="utf-8"))

steps = S["history"]["steps"]
ep = S["history"]["epochs"]
xs = np.array([s["step"] for s in steps])
ys = np.array([s["loss"] for s in steps])

# smoothed train loss
w = 10
if len(ys) >= w:
    kernel = np.ones(w) / w
    smooth = np.convolve(ys, kernel, mode="valid")
    sx = xs[w - 1:]
else:
    smooth, sx = ys, xs

fig, ax = plt.subplots(figsize=(9.5, 5.6), dpi=150)
ax.plot(xs, ys, color="#9ecae1", lw=0.9, alpha=0.75, label="Training loss (per step)")
ax.plot(sx, smooth, color="#08519c", lw=2.2, label=f"Training loss (moving avg, w={w})")

ev = [e["epoch"] * S["config"]["steps_per_epoch"] for e in ep]
vl = [e["val_loss"] for e in ep]
ax.plot(ev, vl, color="#cb181d", marker="o", ms=7, lw=2.2, label="Validation loss (per epoch)")
for x, y in zip(ev, vl):
    ax.annotate(f"{y:.4f}", (x, y), textcoords="offset points", xytext=(0, 9),
                ha="center", fontsize=9, color="#cb181d", fontweight="bold")
for e in ep:
    ax.axvline(e["epoch"] * S["config"]["steps_per_epoch"], color="grey", ls=":", lw=0.9, alpha=0.6)

ax.set_xlabel("Optimization step", fontsize=11)
ax.set_ylabel("Cross-entropy loss", fontsize=11)
ax.set_title("ParsBERT fine-tuning on Persian news (6 classes): training vs validation loss",
             fontsize=11.5, fontweight="bold")
ax.legend(loc="upper right", frameon=True, fontsize=9)
ax.grid(alpha=0.3, ls="--")

txt = "  ".join(f"E{e['epoch']}: F1={e['val_macro_f1']:.3f}" for e in ep)
ax.text(0.01, 0.03, f"epoch-wise val Macro-F1 ->  {txt}", transform=ax.transAxes,
        fontsize=8.5, color="#252525",
        bbox=dict(boxstyle="round,pad=0.35", fc="#f7f7f7", ec="#bdbdbd"))
ax.set_xlim(0, S["config"]["total_steps"])
fig.tight_layout()
out = os.path.join(RUN, "learning_curve.png")
fig.savefig(out, bbox_inches="tight")
fig.savefig(os.path.join(ROOT, "learning_curve.png"), bbox_inches="tight")
print("saved", out)

# also a second view: per-epoch only (loss + F1)
fig2, ax2 = plt.subplots(figsize=(7.2, 4.6), dpi=150)
epx = [e["epoch"] for e in ep]
ax2.plot(epx, [e["train_loss"] for e in ep], marker="o", color="#08519c", label="Train loss")
ax2.plot(epx, [e["val_loss"] for e in ep], marker="s", color="#cb181d", label="Val loss")
ax2.set_xlabel("Epoch"); ax2.set_ylabel("Cross-entropy loss")
ax2.set_title("Loss per epoch", fontweight="bold")
ax2.set_xticks(epx); ax2.grid(alpha=0.3, ls="--"); ax2.legend()
fig2.tight_layout()
fig2.savefig(os.path.join(RUN, "loss_per_epoch.png"), bbox_inches="tight")
print("saved per-epoch")
