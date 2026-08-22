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
        # Arial avoids Calibri ligature glyphs (fi/fl/ti) that Matplotlib
        # rendered as empty entity boxes on the ERD.
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Segoe UI", "DejaVu Sans"],
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

    lang = df["language"].astype(str).str.strip().str.lower()
    lang = lang[lang.isin(["english", "taglish", "filipino"])].value_counts().reindex(
        ["english", "taglish", "filipino"]
    )
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    palette = ["#3D5A4C", "#6F8F7F", "#A3C1B0"]
    wedges, texts, autotexts = ax.pie(
        lang.values,
        labels=[str(x).title() for x in lang.index],
        autopct="%1.1f%%",
        colors=palette,
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
    lines = [ln for ln in str(text).split("\n") if ln != ""]
    n = max(len(lines), 1)
    line_h = min(0.24, (h * 0.78) / n)
    start = y + h / 2 + ((n - 1) * line_h) / 2
    for i, line in enumerate(lines):
        ax.text(
            x + w / 2,
            start - i * line_h,
            line,
            ha="center",
            va="center",
            fontsize=fs,
            fontweight="bold" if bold else "normal",
            color="#1A202C",
            fontfamily="sans-serif",
            clip_on=True,
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
    fig, ax = plt.subplots(figsize=(11.2, 7.4))
    ax.set_xlim(0, 11.2)
    ax.set_ylim(0, 7.4)
    ax.axis("off")
    ax.set_title("Logical data model (simplified)", fontsize=13, pad=8, loc="left")

    def entity(x, y, w, h, title, fields):
        header_h = 0.38
        body = FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.01,rounding_size=0.06",
            linewidth=1.15,
            facecolor="#FAFCFB",
            edgecolor="#3D5A4C",
        )
        ax.add_patch(body)
        header = FancyBboxPatch(
            (x, y + h - header_h),
            w,
            header_h,
            boxstyle="round,pad=0.01,rounding_size=0.06",
            linewidth=0,
            facecolor="#3D5A4C",
            edgecolor="#3D5A4C",
        )
        ax.add_patch(header)
        ax.text(
            x + w / 2,
            y + h - header_h / 2,
            title,
            ha="center",
            va="center",
            fontsize=8.4,
            fontweight="bold",
            color="white",
            fontfamily="sans-serif",
        )
        n = len(fields)
        usable = h - header_h - 0.12
        line_h = usable / max(n, 1)
        top = y + h - header_h - 0.08
        for i, field in enumerate(fields):
            ax.text(
                x + 0.12,
                top - i * line_h,
                field,
                ha="left",
                va="top",
                fontsize=7.2,
                color="#1A202C",
                fontfamily="sans-serif",
            )

    entity(0.2, 4.55, 3.45, 2.55, "users", [
        "PK  id",
        "nickname, email, password_hash",
        "profile fields, avatar_data_url",
        "totp_secret, totp_enabled",
        "ui_preferences_json",
        "is_disabled, last_login",
        "privacy_agreed_at",
    ])
    entity(3.85, 4.55, 3.55, 2.55, "journal_entries", [
        "PK  id",
        "FK  user_id  →  users.id",
        "title, text_content, tags_json",
        "emotion / sentiment labels & scores",
        "all_probs_json, image_urls_json",
        "entry_datetime_utc, timestamps",
    ])
    entity(7.6, 5.15, 3.35, 1.95, "user_tags", [
        "PK  (user_id, tag)",
        "FK  user_id  →  users.id",
        "icon_name",
    ])
    entity(0.2, 2.35, 3.45, 1.9, "pending_registrations", [
        "PK  email",
        "otp_code, otp_expires_at",
        "profile fields pending verify",
    ])
    entity(3.85, 2.35, 3.55, 1.9, "password_resets", [
        "PK  email",
        "reset_code, expires_at",
    ])
    entity(7.6, 2.35, 3.35, 1.9, "push_subscriptions", [
        "PK  id",
        "FK  user_id  →  users.id",
        "endpoint, subscription_json",
    ])
    entity(0.2, 0.2, 3.45, 1.85, "login_lockouts", [
        "account key, failed attempts",
        "lock expiry",
        "otp_resend_limits_* (per flow)",
    ])
    entity(3.85, 0.2, 3.55, 1.85, "2FA / OTP challenges", [
        "login_totp_challenges",
        "login_totp_recovery_otps",
        "email / password change OTPs",
    ])
    entity(7.6, 0.2, 3.35, 1.85, "admin & settings", [
        "admin_audit_logs",
        "system_settings",
    ])

    ax.annotate("", xy=(3.85, 6.0), xytext=(3.65, 6.0), arrowprops=dict(arrowstyle="-|>", color="#4A5568", lw=1.1))
    ax.annotate("", xy=(7.6, 6.35), xytext=(7.4, 6.35), arrowprops=dict(arrowstyle="-|>", color="#4A5568", lw=1.1))
    ax.annotate("", xy=(9.27, 4.25), xytext=(9.27, 5.15), arrowprops=dict(arrowstyle="-|>", color="#4A5568", lw=1.1))
    save(fig, "diagram-erd.png")


if __name__ == "__main__":
    dataset_charts()
    architecture()
    ml_pipeline()
    erd()
    print("done")
