"""Generate charts and architecture diagrams for DiariCore documentation."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import pandas as pd

ROOT = Path(__file__).resolve().parent
FIG = ROOT / "figures"
FIG.mkdir(parents=True, exist_ok=True)
DATASET = Path(
    r"C:\Users\lawre\OneDrive\Desktop\myproject\DCore\FinalProject_Resources\1500_dataset_expanded.xlsx"
)

plt.rcParams.update(
    {
        "font.family": "Calibri",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#4A5568",
        "axes.labelcolor": "#1A202C",
        "text.color": "#1A202C",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.grid": True,
        "grid.color": "#E2E8F0",
        "grid.linewidth": 0.6,
    }
)

COLORS = {
    "neutral": "#94A3B8",
    "angry": "#C45C4A",
    "sad": "#5B7C99",
    "happy": "#C9A227",
    "anxious": "#7C6BAD",
}


def save(fig, name: str):
    out = FIG / name
    fig.savefig(out, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", out)


def dataset_charts():
    df = pd.read_excel(DATASET)
    order = ["neutral", "angry", "sad", "happy", "anxious"]
    counts = df["label"].value_counts().reindex(order)

    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    bars = ax.bar(counts.index.str.title(), counts.values, color=[COLORS[k] for k in order], width=0.62)
    ax.set_ylabel("Number of samples")
    ax.set_title("Training dataset — emotion label distribution (n = 1,593)")
    ax.set_axisbelow(True)
    for b, v in zip(bars, counts.values):
        ax.text(b.get_x() + b.get_width() / 2, v + 4, str(int(v)), ha="center", va="bottom", fontsize=9)
    ax.set_ylim(0, max(counts.values) * 1.14)
    save(fig, "chart-label-distribution.png")

    lang = df["language"].value_counts()
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    palette = ["#3D5A4C", "#6F8F7F", "#A3C1B0", "#CBD5D1"]
    wedges, texts, autotexts = ax.pie(
        lang.values,
        labels=[str(x).title() for x in lang.index],
        autopct="%1.1f%%",
        colors=palette[: len(lang)],
        startangle=90,
        textprops={"fontsize": 9},
    )
    for t in autotexts:
        t.set_color("white")
        t.set_fontsize(8)
    ax.set_title("Training dataset — language distribution")
    save(fig, "chart-language-distribution.png")


def box(ax, x, y, w, h, text, fc="#F7FAF8", ec="#3D5A4C", fs=8.2, bold=False):
    p = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.012,rounding_size=0.08",
        linewidth=1.15,
        facecolor=fc,
        edgecolor=ec,
    )
    ax.add_patch(p)
    ax.text(
        x + w / 2,
        y + h / 2,
        text,
        ha="center",
        va="center",
        fontsize=fs,
        fontweight="bold" if bold else "normal",
        wrap=True,
        color="#1A202C",
    )
    return p


def arrow(ax, x1, y1, x2, y2):
    ax.annotate(
        "",
        xy=(x2, y2),
        xytext=(x1, y1),
        arrowprops=dict(arrowstyle="-|>", color="#4A5568", lw=1.15),
    )


def architecture():
    fig, ax = plt.subplots(figsize=(10.2, 6.4))
    ax.set_xlim(0, 10.2)
    ax.set_ylim(0, 6.4)
    ax.axis("off")
    ax.set_title("DiariCore — current runtime architecture", fontsize=13, pad=8, loc="left")

    box(ax, 0.25, 5.35, 2.2, 0.75, "User\nBrowser / Installed PWA", fc="#EEF4F1", bold=True)
    box(ax, 3.15, 5.35, 3.7, 0.75, "Railway web service\nFlask + Gunicorn  (diaricore.up.railway.app)", fc="#E8F0EC", bold=True)
    box(ax, 7.4, 5.35, 2.5, 0.75, "Railway Postgres\njournal, users, auth", fc="#F4F1EA", bold=True)

    box(ax, 0.25, 3.85, 2.2, 0.85, "Static assets\nService worker cache\nWeb App Manifest", fc="#F7FAF8")
    box(ax, 3.15, 3.7, 3.7, 1.15, "Application modules\nAuth, journal CRUD, uploads,\ninsights APIs, push dispatcher", fc="#F7FAF8")
    box(ax, 7.4, 3.85, 2.5, 0.85, "Persistent volume\n/data/uploads", fc="#F4F1EA")

    box(ax, 0.25, 2.15, 2.35, 1.05, "Hugging Face Space\nONNX inference\nPOST /predict", fc="#EDE9F6", ec="#5B4B8A", bold=True)
    box(ax, 2.9, 2.15, 2.35, 1.05, "Hugging Face Hub\nFine-tuned XLM-RoBERTa\nONNX + tokenizer", fc="#EDE9F6", ec="#5B4B8A")
    box(ax, 5.55, 2.15, 2.1, 1.05, "Brevo\nTransactional email\nOTP / reset / recovery", fc="#F8EEE8", ec="#A86B4A")
    box(ax, 7.9, 2.15, 2.0, 1.05, "HF Inference\nWhisper ASR\n(voice fallback)", fc="#EDE9F6", ec="#5B4B8A")

    box(ax, 0.25, 0.45, 3.3, 1.05, "Google Authenticator (user device)\nTOTP codes for optional 2FA", fc="#EEF2F7", ec="#4A6278")
    box(ax, 3.8, 0.45, 3.1, 1.05, "Optional cron-job.org\nPOST /api/internal/push/dispatch\nif internal scheduler is disabled", fc="#EEF2F7", ec="#4A6278")
    box(ax, 7.15, 0.45, 2.75, 1.05, "Web Push (VAPID)\nInstalled PWA devices", fc="#EEF2F7", ec="#4A6278")

    arrow(ax, 2.45, 5.72, 3.15, 5.72)
    arrow(ax, 6.85, 5.72, 7.4, 5.72)
    arrow(ax, 5.0, 5.35, 5.0, 4.85)
    arrow(ax, 4.2, 3.7, 1.45, 3.2)
    arrow(ax, 5.8, 3.7, 6.55, 3.2)
    arrow(ax, 6.2, 3.7, 8.7, 3.2)
    arrow(ax, 1.4, 2.15, 1.9, 1.5)
    arrow(ax, 5.0, 3.7, 5.35, 1.5)
    save(fig, "diagram-runtime-architecture.png")


def ml_pipeline():
    fig, ax = plt.subplots(figsize=(10.2, 3.35))
    ax.set_xlim(0, 10.2)
    ax.set_ylim(0, 3.35)
    ax.axis("off")
    ax.set_title("Emotion model workflow (training to inference)", fontsize=13, pad=6, loc="left")
    steps = [
        (0.15, "Dataset\n1,593 labeled\njournal texts"),
        (2.15, "Google Colab\nFine-tune\nXLM-RoBERTa-Base"),
        (4.15, "Evaluate\nTest Acc 0.8370\nMacro F1 0.8384"),
        (6.15, "Export artifacts\nONNX + tokenizer\nto HF Hub"),
        (8.15, "HF Space\n/predict → Railway\njournal save/re-analyze"),
    ]
    for x, t in steps:
        box(ax, x, 0.85, 1.85, 1.55, t, fc="#F3F7F5", fs=8)
    for i in range(len(steps) - 1):
        x1 = steps[i][0] + 1.85
        x2 = steps[i + 1][0]
        arrow(ax, x1, 1.62, x2, 1.62)
    save(fig, "diagram-ml-pipeline.png")


def erd():
    fig, ax = plt.subplots(figsize=(10.2, 6.8))
    ax.set_xlim(0, 10.2)
    ax.set_ylim(0, 6.8)
    ax.axis("off")
    ax.set_title("Logical data model (simplified)", fontsize=13, pad=6, loc="left")

    tables = [
        (0.2, 4.55, 3.1, 2.05, "users\nPK id\nnickname, email, password_hash\nprofile fields, avatar\ntotp_*, ui_preferences_json\nis_disabled, last_login"),
        (3.6, 4.85, 3.15, 1.75, "journal_entries\nPK id   FK user_id\ntitle, text_content, tags_json\nemotion/sentiment scores\nall_probs_json, image_urls_json\nentry_datetime_utc"),
        (7.05, 5.05, 2.9, 1.55, "user_tags\nPK (user_id, tag)\nicon_name"),
        (0.2, 2.55, 3.1, 1.55, "pending_registrations\nPK email\notp_code, otp_expires_at"),
        (3.6, 2.55, 3.15, 1.55, "password_resets\nPK email\nreset_code, expires_at"),
        (7.05, 2.55, 2.9, 1.55, "push_subscriptions\nPK id   FK user_id\nendpoint, subscription_json"),
        (0.2, 0.35, 3.1, 1.75, "login_lockouts\notp_resend_limits_*\n(per-flow rate tables)"),
        (3.6, 0.35, 3.15, 1.75, "login_totp_challenges\nlogin_totp_recovery_otps\nemail/password change challenges"),
        (7.05, 0.35, 2.9, 1.75, "admin_audit_logs\nsystem_settings"),
    ]
    for x, y, w, h, t in tables:
        box(ax, x, y, w, h, t, fs=7.4, fc="#FAFCFB")
    save(fig, "diagram-erd.png")


if __name__ == "__main__":
    dataset_charts()
    architecture()
    ml_pipeline()
    erd()
    print("done")
