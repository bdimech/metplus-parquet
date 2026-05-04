"""Build METplus to Parquet summary presentation using the bureau template."""

import io
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import pyarrow.parquet as pq
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR_TYPE
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

# ── Colours (from template) ────────────────────────────────────────────────────
BLUE    = RGBColor(0x24, 0x61, 0xE5)
LBLUE   = RGBColor(0xEB, 0xF3, 0xFF)
MBLUEBG = RGBColor(0xD0, 0xE2, 0xFF)
DARK    = RGBColor(0x2D, 0x2D, 0x2D)
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
LGREY   = RGBColor(0xF2, 0xF2, 0xF2)
MGREY   = RGBColor(0xCC, 0xCC, 0xCC)
GREEN   = RGBColor(0x10, 0x7C, 0x10)
LGREEN  = RGBColor(0xE8, 0xF5, 0xE9)
ORANGE  = RGBColor(0xCC, 0x50, 0x00)
LORANGE = RGBColor(0xFE, 0xF0, 0xE7)
SGREY   = RGBColor(0x60, 0x60, 0x60)


def i(v): return Inches(v)
def p(v): return Pt(v)


# ── Open template, strip existing slides ───────────────────────────────────────
prs = Presentation("METplus - Application Support.pptx")
sldIdLst = prs.slides._sldIdLst
while len(sldIdLst):
    prs.part.drop_rel(sldIdLst[0].get(qn("r:id")))
    del sldIdLst[0]

LAYOUT = prs.slide_layouts[6]   # "03 Content Slide_Text and images"


# ── Shape helpers ──────────────────────────────────────────────────────────────
def new_slide():
    return prs.slides.add_slide(LAYOUT)


def add_title(slide, text):
    tb = slide.shapes.add_textbox(i(0.56), i(0.47), i(12.5), i(0.55))
    tf = tb.text_frame
    run = tf.paragraphs[0].add_run()
    run.text = text
    run.font.bold = True
    run.font.size = p(24)
    run.font.color.rgb = BLUE


def rect(slide, left, top, w, h, text="",
         fill=LBLUE, fg=DARK, border=BLUE, bw=0.75,
         fs=10, bold=False, align=PP_ALIGN.CENTER, wrap=True):
    shp = slide.shapes.add_shape(1, i(left), i(top), i(w), i(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    shp.line.color.rgb = border
    shp.line.width = p(bw)
    tf = shp.text_frame
    tf.word_wrap = wrap
    tf.margin_left  = i(0.06)
    tf.margin_right = i(0.06)
    tf.margin_top   = i(0.04)
    tf.margin_bottom= i(0.04)
    para = tf.paragraphs[0]
    para.alignment = align
    run = para.add_run()
    run.text = text
    run.font.color.rgb = fg
    run.font.size = p(fs)
    run.font.bold = bold
    return shp


def tbx(slide, left, top, w, h, lines,
        fs=10, color=DARK, bold=False, align=PP_ALIGN.LEFT):
    tb = slide.shapes.add_textbox(i(left), i(top), i(w), i(h))
    tf = tb.text_frame
    tf.word_wrap = True
    for idx, line in enumerate(lines):
        para = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        para.alignment = align
        run = para.add_run()
        run.text = line
        run.font.size = p(fs)
        run.font.color.rgb = color
        run.font.bold = bold
    return tb


def arrow(slide, x1, y1, x2, y2, color=BLUE, w=1.5):
    c = slide.shapes.add_connector(
        MSO_CONNECTOR_TYPE.STRAIGHT, i(x1), i(y1), i(x2), i(y2))
    c.line.color.rgb = color
    c.line.width = p(w)
    return c


def hline(slide, left, top, w, color=MGREY, lw=0.75):
    shp = slide.shapes.add_shape(1, i(left), i(top), i(w), i(0.01))
    shp.fill.solid()
    shp.fill.fore_color.rgb = color
    shp.line.color.rgb = color
    shp.line.width = p(lw)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 1 — What We Get: METplus Output Files
# ══════════════════════════════════════════════════════════════════════════════
s1 = new_slide()
add_title(s1, "What We Get: METplus Verification Outputs")

tbx(s1, 0.5, 1.15, 5.8, 5.5, [
    "METplus runs routine NWP verification and writes",
    "results to structured output folders.",
    "",
    "Each configuration produces a folder named:",
    "  <Model>_<Obs>_<Parameter>_<Timestep>",
    "",
    "Inside each folder are daily YYYYMMDDHH",
    "subdirectories, each containing .stat files",
    "for every forecast lead time and domain.",
    "",
    "Two types of verification output:",
    "",
    "  GridStat  — deterministic scores",
    "  (bias, RMSE, MAE)",
    "",
    "  EnsembleStat — ensemble scores",
    "  (CRPS, Spread, Skill Score)",
], fs=11)

# Right: folder tree diagram
RX = 6.8
rect(s1, RX, 1.1, 6.2, 0.4, "input_all/",
     fill=BLUE, fg=WHITE, fs=10, bold=True, border=BLUE)

# Two branch boxes
rect(s1, RX,       1.7, 3.0, 0.38,
     "AGlobal4_Analysis_T_AllLevels_00Z/",
     fill=LBLUE, fg=DARK, fs=8.5, border=BLUE, bw=0.5)
rect(s1, RX + 3.1, 1.7, 3.0, 0.38,
     "AGlobal4E_Analysis_T850_00Z/",
     fill=LBLUE, fg=DARK, fs=8.5, border=BLUE, bw=0.5)

# Lines from top box to branches
arrow(s1, RX + 1.5, 1.5, RX + 1.5, 1.7,  color=MGREY, w=1)
arrow(s1, RX + 4.6, 1.5, RX + 4.6, 1.7,  color=MGREY, w=1)
arrow(s1, RX + 1.5, 1.5, RX + 4.6, 1.5,  color=MGREY, w=1)

# GridStat subfolder (left branch)
rect(s1, RX, 2.25, 3.0, 0.35, "GridStat/  2026041000/",
     fill=LGREY, fg=DARK, fs=8.5, border=MGREY, bw=0.5)

# File type pills
rect(s1, RX,       2.77, 0.92, 0.28, "_cnt.txt",
     fill=LGREEN, fg=GREEN, fs=8, border=GREEN, bw=0.5)
rect(s1, RX+0.97,  2.77, 0.98, 0.28, "_sl1l2.txt",
     fill=LGREEN, fg=GREEN, fs=8, border=GREEN, bw=0.5)
rect(s1, RX+2.0,   2.77, 0.98, 0.28, "_sal1l2.txt",
     fill=LGREEN, fg=GREEN, fs=8, border=GREEN, bw=0.5)

# EnsembleStat (right branch — two sub-folders)
rect(s1, RX+3.1,   2.25, 1.45, 0.35, "GridStat/",
     fill=LGREY, fg=DARK, fs=8.5, border=MGREY, bw=0.5)
rect(s1, RX+4.65,  2.25, 1.45, 0.35, "EnsembleStat/",
     fill=LGREY, fg=DARK, fs=8.5, border=MGREY, bw=0.5)
rect(s1, RX+3.1,   2.77, 1.45, 0.28, "_cnt.txt",
     fill=LGREEN, fg=GREEN, fs=8, border=GREEN, bw=0.5)
rect(s1, RX+4.65,  2.77, 1.45, 0.28, "_ecnt.txt",
     fill=LORANGE, fg=ORANGE, fs=8, border=ORANGE, bw=0.5)

# Legend
hline(s1, RX, 3.25, 6.2)
tbx(s1, RX, 3.35, 6.2, 0.3, ["Legend:"], fs=8.5, color=SGREY, bold=True)
rect(s1, RX,      3.65, 1.0, 0.28, "GridStat",
     fill=LGREEN, fg=GREEN, fs=8, border=GREEN, bw=0.5)
tbx(s1, RX+1.1,   3.65, 2.0, 0.3, ["Deterministic stats (CNT, SL1L2, SAL1L2)"],
    fs=8.5, color=DARK)
rect(s1, RX+3.1,  3.65, 1.2, 0.28, "EnsembleStat",
     fill=LORANGE, fg=ORANGE, fs=8, border=ORANGE, bw=0.5)
tbx(s1, RX+4.4,   3.65, 2.0, 0.3, ["Ensemble stats (ECNT)"],
    fs=8.5, color=DARK)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 2 — What We Do: Conversion Pipeline
# ══════════════════════════════════════════════════════════════════════════════
s2 = new_slide()
add_title(s2, "What We Do: Conversion Pipeline")

BW, BH = 2.2, 0.65
FY = 2.5   # flow box top
XS = [0.45, 2.95, 5.45, 7.95, 10.45]

titles2 = ["Input Folders", "Read & Parse",
           "Merge & Clean", "Group by\nModel / Obs", "Parquet Files"]
fills2  = [LBLUE, LBLUE, LBLUE, LBLUE, LGREEN]
bords2  = [BLUE,  BLUE,  BLUE,  BLUE,  GREEN]
fgs2    = [DARK,  DARK,  DARK,  DARK,  GREEN]

for k, (x, t, f, b, fg) in enumerate(zip(XS, titles2, fills2, bords2, fgs2)):
    rect(s2, x, FY, BW, BH, t, fill=f, fg=fg, border=b,
         fs=11, bold=True, bw=1.0)
    if k < len(XS) - 1:
        arrow(s2, x + BW, FY + BH/2, XS[k+1], FY + BH/2)

subs2 = [
    ["Config folders:", "<Model>_<Obs>_<Param>_<TS>",
     "GridStat/ or EnsembleStat/", "YYYYMMDDHH subdirectories"],
    ["CNT, SL1L2, SAL1L2", "(GridStat)", "ECNT", "(EnsembleStat)"],
    ["Drop metadata cols", "Convert lead → hours", "Add PARAMETER column",
     "Numeric type casting"],
    ["One output per", "model + obs pair:", "AGlobal4_Analysis",
     "AGlobal4E_Analysis"],
    ["One .parquet per", "model/obs pair", "All parameters", "All timesteps"],
]
for x, sub in zip(XS, subs2):
    tbx(s2, x, FY + BH + 0.12, BW, 1.5, sub,
        fs=9, color=DARK, align=PP_ALIGN.CENTER)

rect(s2, 2.0, 5.05, 9.2, 0.5,
     "Re-running is safe — already-loaded init dates are skipped per PARAMETER and STAT_TYPE",
     fill=LGREY, fg=SGREY, border=MGREY, bw=0.5, fs=9.5)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 3 — What the Outputs Look Like
# ══════════════════════════════════════════════════════════════════════════════
s3 = new_slide()
add_title(s3, "What the Outputs Look Like: Parquet Schema")

tbx(s3, 0.5, 1.1, 12.5, 0.4,
    ["Each row = one unique combination of init date, lead time, pressure level, domain, parameter, and stat type."],
    fs=10.5)

# Column header row
CDEFS = [
    # (label,       left,  width, fill,    fg,     border)
    ("PARAMETER",   0.45,  1.65,  BLUE,    WHITE,  BLUE),
    ("STAT_TYPE",   2.15,  1.55,  BLUE,    WHITE,  BLUE),
    ("INIT_DATE",   3.75,  1.55,  BLUE,    WHITE,  BLUE),
    ("FCST_LEAD_H", 5.35,  1.4,   BLUE,    WHITE,  BLUE),
    ("FCST_LEV",    6.8,   1.35,  BLUE,    WHITE,  BLUE),
    ("VX_MASK",     8.2,   1.35,  BLUE,    WHITE,  BLUE),
    ("ME / RMSE / MAE", 9.6, 1.75, GREEN,  WHITE,  GREEN),
    ("CRPS / SPREAD", 11.4, 1.8,  ORANGE,  WHITE,  ORANGE),
]
HY = 1.6
RH = 0.32

for lbl, cx, cw, f, fg, b in CDEFS:
    rect(s3, cx, HY, cw, RH, lbl,
         fill=f, fg=fg, border=b, bw=0, fs=8.5, bold=True)

# Data rows
DATA = [
    ("T_AllLevels",    "GridStat",      "2026-04-10", "24",  "P850", "Australia", "−0.5 / 1.87 / 1.43", "—"),
    ("MSLP",           "GridStat",      "2026-04-10", "48",  "L0",   "NH",        "0.3 / 2.1 / 1.8",    "—"),
    ("T850",           "EnsembleStat",  "2026-04-15", "24",  "P850", "NH",        "0.28 / 3.26 / 2.26", "1.62 / 2.73"),
    ("Wind_AllLevels", "GridStat",      "2026-04-15", "72",  "P250", "SH",        "0.1 / 2.4 / 1.9",    "—"),
]
for ri, row in enumerate(DATA):
    ry = HY + RH + ri * RH
    rbg = WHITE if ri % 2 == 0 else LGREY
    vals = list(row)
    for ci, (lbl, cx, cw, _f, _fg, _b) in enumerate(CDEFS):
        cell_fill = rbg
        cell_fg   = DARK
        if ci == 1 and vals[ci] == "EnsembleStat":
            cell_fill = LORANGE
            cell_fg   = ORANGE
        elif ci == 1:
            cell_fill = LGREEN
            cell_fg   = GREEN
        rect(s3, cx, ry, cw, RH, vals[ci],
             fill=cell_fill, fg=cell_fg,
             border=RGBColor(0xDD, 0xDD, 0xDD), bw=0.3, fs=8.5)

legend_y = HY + RH * (1 + len(DATA)) + 0.18
rect(s3, 0.45,  legend_y, 1.4, 0.28, "Index columns",
     fill=BLUE,   fg=WHITE,  border=BLUE,   bw=0, fs=8)
rect(s3, 1.95,  legend_y, 1.4, 0.28, "GridStat stats",
     fill=GREEN,  fg=WHITE,  border=GREEN,  bw=0, fs=8)
rect(s3, 3.45,  legend_y, 1.6, 0.28, "EnsembleStat stats",
     fill=ORANGE, fg=WHITE,  border=ORANGE, bw=0, fs=8)

tbx(s3, 0.45, legend_y + 0.38, 12.5, 0.4,
    ["Constant columns (model, variable, units, obs type) are stripped from rows and embedded as file-level Parquet metadata."],
    fs=9, color=SGREY)


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 4 — How We Can Use the Data
# ══════════════════════════════════════════════════════════════════════════════
s4 = new_slide()
add_title(s4, "How We Can Use the Data")

USE = [
    ("Single Model\nExploration",
     "Load one model's file, filter to a\nparameter, level and domain, and\nplot any metric by lead time.",
     LBLUE, BLUE),
    ("Cross-Model\nComparison",
     "Load two files side-by-side, filter\nto the same parameter and domain,\nand compare RMSE or bias.",
     LBLUE, BLUE),
    ("Ensemble\nDiagnostics",
     "Filter STAT_TYPE = EnsembleStat\nto access CRPS and Spread.\nCheck Spread ≈ RMSE for calibration.",
     LORANGE, ORANGE),
]
for ui, (ut, ud, uf, ub) in enumerate(USE):
    uy = 1.15 + ui * 1.9
    rect(s4, 0.45, uy, 2.3, 0.55, ut,
         fill=uf, fg=ub, border=ub, bw=1.0, fs=11, bold=True)
    tbx(s4, 0.45, uy + 0.62, 2.5, 1.1,
        ud.split("\n"), fs=10, color=DARK)

# Code box (dark background)
CODE_LINES = [
    ("import pyarrow.parquet as pq",                  "kw"),
    ("",                                               ""),
    ("# Load a model dataset",                         "cm"),
    ("g4 = pq.read_table(",                            "tx"),
    ("    'AGlobal4_Analysis.parquet'",                "st"),
    (").to_pandas()",                                  "tx"),
    ("",                                               ""),
    ("# Filter to one parameter",                      "cm"),
    ("t = g4[g4['PARAMETER'] == 'T_AllLevels']",      "tx"),
    ("",                                               ""),
    ("# Cross-model comparison",                       "cm"),
    ("g4e = pq.read_table(",                           "tx"),
    ("    'AGlobal4E_Analysis.parquet',",              "st"),
    ("    filters=[('PARAMETER','=','MSLP')]",         "tx"),
    (").to_pandas()",                                  "tx"),
    ("",                                               ""),
    ("# Ensemble stats only",                          "cm"),
    ("ens = g4e[",                                     "tx"),
    ("    g4e['STAT_TYPE'] == 'EnsembleStat']",        "tx"),
]
COLORS = {
    "kw": RGBColor(0x56, 0x9C, 0xD6),
    "cm": RGBColor(0x6A, 0x99, 0x55),
    "st": RGBColor(0xCE, 0x91, 0x78),
    "tx": RGBColor(0xCE, 0xD1, 0xD8),
    "":   RGBColor(0xCE, 0xD1, 0xD8),
}
code_shp = s4.shapes.add_shape(1, i(3.1), i(1.1), i(10.1), i(5.5))
code_shp.fill.solid()
code_shp.fill.fore_color.rgb = RGBColor(0x1E, 0x1E, 0x2E)
code_shp.line.color.rgb = RGBColor(0x44, 0x44, 0x66)
code_shp.line.width = p(0.5)
tf = code_shp.text_frame
tf.word_wrap = False
tf.margin_left  = i(0.18)
tf.margin_top   = i(0.12)
tf.margin_bottom= i(0.08)
for li, (line, kind) in enumerate(CODE_LINES):
    para = tf.paragraphs[0] if li == 0 else tf.add_paragraph()
    run  = para.add_run()
    run.text = line
    run.font.size = p(9.5)
    run.font.color.rgb = COLORS[kind]


# ══════════════════════════════════════════════════════════════════════════════
# SLIDE 5 — Example Results (real charts from output_all/)
# ══════════════════════════════════════════════════════════════════════════════
s5 = new_slide()
add_title(s5, "Example Results")

G4_PATH  = Path("output_all/AGlobal4_Analysis.parquet")
G4E_PATH = Path("output_all/AGlobal4E_Analysis.parquet")

if G4_PATH.exists() and G4E_PATH.exists():
    g4  = pq.read_table(G4_PATH).to_pandas()
    g4e = pq.read_table(G4E_PATH).to_pandas()

    # Chart 1: MSLP RMSE by lead — AGlobal4 vs AGlobal4E
    fig1, ax1 = plt.subplots(figsize=(6.0, 3.6), dpi=150)
    for label_m, df_m, col_m in [("AGlobal4", g4, "#2461E5"),
                                   ("AGlobal4E", g4e, "#CC5000")]:
        sub = df_m[
            (df_m["PARAMETER"] == "MSLP") &
            (df_m["STAT_TYPE"] == "GridStat") &
            (df_m["FCST_LEV"]  == "L0") &
            (df_m["VX_MASK"]   == "NH")
        ]
        if not sub.empty:
            s = sub.groupby("FCST_LEAD_H")["RMSE"].mean()
            ax1.plot(s.index, s.values, marker="o", label=label_m,
                     color=col_m, linewidth=2, markersize=5)
    ax1.set_xlabel("Forecast Lead Time (hours)", fontsize=10)
    ax1.set_ylabel("RMSE (hPa)", fontsize=10)
    ax1.set_title("MSLP — RMSE by Lead Time (NH)", fontsize=11, fontweight="bold")
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.25, linestyle="--")
    fig1.tight_layout()
    buf1 = io.BytesIO()
    fig1.savefig(buf1, format="png", bbox_inches="tight")
    buf1.seek(0)
    plt.close(fig1)

    # Chart 2: T850 Spread vs RMSE — AGlobal4E EnsembleStat
    fig2, ax2 = plt.subplots(figsize=(6.0, 3.6), dpi=150)
    ens = g4e[
        (g4e["PARAMETER"] == "T850") &
        (g4e["STAT_TYPE"] == "EnsembleStat") &
        (g4e["FCST_LEV"]  == "P850") &
        (g4e["VX_MASK"]   == "NH")
    ]
    if not ens.empty:
        spread = ens.groupby("FCST_LEAD_H")["SPREAD"].mean()
        rmse   = ens.groupby("FCST_LEAD_H")["RMSE"].mean()
        ax2.plot(spread.index, spread.values, marker="o", label="Spread",
                 color="#CC5000", linewidth=2, markersize=5)
        ax2.plot(rmse.index,   rmse.values,   marker="s", label="RMSE",
                 color="#2461E5", linewidth=2, markersize=5)
    ax2.set_xlabel("Forecast Lead Time (hours)", fontsize=10)
    ax2.set_ylabel("Value (K)", fontsize=10)
    ax2.set_title("AGlobal4E T850 — Spread vs RMSE (NH)", fontsize=11, fontweight="bold")
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.25, linestyle="--")
    fig2.tight_layout()
    buf2 = io.BytesIO()
    fig2.savefig(buf2, format="png", bbox_inches="tight")
    buf2.seek(0)
    plt.close(fig2)

    s5.shapes.add_picture(buf1, i(0.4),  i(1.1), i(6.2), i(3.9))
    s5.shapes.add_picture(buf2, i(6.85), i(1.1), i(6.2), i(3.9))

    tbx(s5, 0.4,  5.1, 6.2, 0.4,
        ["Cross-model comparison: MSLP RMSE by lead time over the Northern Hemisphere."],
        fs=9, color=SGREY, align=PP_ALIGN.CENTER)
    tbx(s5, 6.85, 5.1, 6.2, 0.4,
        ["Ensemble calibration check: Spread ≈ RMSE indicates a well-calibrated ensemble."],
        fs=9, color=SGREY, align=PP_ALIGN.CENTER)

    tbx(s5, 0.45, 5.65, 12.5, 0.8, [
        "Loaded with:   pq.read_table('AGlobal4_Analysis.parquet', filters=[('PARAMETER','=','MSLP')]).to_pandas()",
        "Filtered with: df[df['STAT_TYPE'] == 'EnsembleStat'] | df[df['VX_MASK'] == 'NH']",
    ], fs=8.5, color=SGREY)
else:
    tbx(s5, 0.5, 2.5, 12.0, 1.0,
        ["Run convert_all() first to generate output_all/, then re-run make_pptx.py to embed real charts."],
        fs=12, color=DARK)

# ── Save ───────────────────────────────────────────────────────────────────────
out = "METplus - Parquet Summary.pptx"
prs.save(out)
print(f"Saved: {out}")
