"""
visualize.py
────────────
사용법:
  python visualize.py --config configs/simple_baseline.yaml

생성 파일:
  results/{run}/cycle_Ts.png   T-s 선도
  results/{run}/cycle_Ph.png   P-h 선도
  results/{run}/cop_vs_rp.png  압력비 파라미터 스윕
  results/{run}/cop_vs_rp.csv
"""

import argparse
import copy
import os
import sys
import csv

import numpy as np
import matplotlib
matplotlib.use("Agg")          # 창 없이 파일 저장
import matplotlib.pyplot as plt
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from cycle_solver import solve
import CoolProp.CoolProp as CP


# ─────────────────────────────────────────────
# 보조 함수
# ─────────────────────────────────────────────

def isobaric_path(T_start_K: float, T_end_K: float, P_Pa: float,
                  fluid: str, N: int = 80):
    """등압 과정 T-s, P-h 경로 생성."""
    T = np.linspace(T_start_K, T_end_K, N)
    s = np.array([CP.PropsSI("S", "T", t, "P", P_Pa, fluid) for t in T])
    h = np.array([CP.PropsSI("H", "T", t, "P", P_Pa, fluid) for t in T])
    return T, s, h


def linear_path(s1, s2, T1, T2, h1, h2, N: int = 30):
    """압축기/터빈 (비등엔트로피) 선형 경로."""
    s = np.linspace(s1, s2, N)
    T = np.linspace(T1, T2, N)
    h = np.linspace(h1, h2, N)
    return T, s, h


# ─────────────────────────────────────────────
# T-s 선도
# ─────────────────────────────────────────────

def plot_Ts(out: dict, cfg: dict, save_path: str) -> None:
    fluid = cfg["fluid"]
    s1, s2, s2p, s3 = [st.s for st in out["states"]]
    T1, T2, T2p, T3 = [st.T for st in out["states"]]
    P_low  = cfg["P_low"]
    P_high = out["P_high"]

    # 각 과정 경로
    T_c,  s_c,  _ = linear_path(s1,  s2,  T1,  T2,  0, 0)   # 압축기
    T_hx, s_hx, _ = isobaric_path(T2, T2p, P_high, fluid)    # Hot HX
    T_t,  s_t,  _ = linear_path(s2p, s3,  T2p, T3,  0, 0)   # 터빈
    T_cx, s_cx, _ = isobaric_path(T3, T1,  P_low,  fluid)    # Cold HX

    fig, ax = plt.subplots(figsize=(7, 5))

    ax.plot(s_c  / 1e3, T_c   - 273.15, "b-",  lw=1.8, label="Compressor (1→2)")
    ax.plot(s_hx / 1e3, T_hx  - 273.15, "r-",  lw=1.8, label="Hot HX (2→2')")
    ax.plot(s_t  / 1e3, T_t   - 273.15, "g-",  lw=1.8, label="Turbine (2'→3)")
    ax.plot(s_cx / 1e3, T_cx  - 273.15, "m-",  lw=1.8, label="Cold HX (3→1)")

    # 상태점 마커
    states_s = [s1, s2, s2p, s3]
    states_T = [T1, T2, T2p, T3]
    labels   = ["1", "2", "2'", "3"]
    ax.scatter([s / 1e3 for s in states_s],
               [T - 273.15 for T in states_T],
               color="k", zorder=5, s=50)
    offsets = [(-18, 5), (5, 5), (5, 5), (5, -12)]
    for lbl, sx, Tx, off in zip(labels, states_s, states_T, offsets):
        ax.annotate(lbl, (sx / 1e3, Tx - 273.15),
                    xytext=off, textcoords="offset points", fontsize=10, fontweight="bold")

    ax.axhline(0,   color="gray", lw=0.6, ls="--")
    ax.axhline(-100, color="gray", lw=0.6, ls="--")

    ax.set_xlabel("Entropy  s  [kJ/(kg·K)]", fontsize=11)
    ax.set_ylabel("Temperature  T  [°C]",    fontsize=11)
    ax.set_title(f"T-s Diagram  |  Air  |  r_p = {out['pressure_ratio']:.2f}  |  COP = {out['COP']:.3f}",
                 fontsize=11)
    ax.legend(fontsize=9, loc="upper left")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"    cycle_Ts.png  saved")


# ─────────────────────────────────────────────
# P-h 선도
# ─────────────────────────────────────────────

def plot_Ph(out: dict, cfg: dict, save_path: str) -> None:
    fluid = cfg["fluid"]
    h1, h2, h2p, h3 = [st.h for st in out["states"]]
    T1, T2, T2p, T3 = [st.T for st in out["states"]]
    P_low  = cfg["P_low"]
    P_high = out["P_high"]

    # 각 과정 경로
    _, _, h_c  = linear_path(0, 0, T1,  T2,  h1,  h2)           # 압축기
    P_c        = np.linspace(P_low, P_high, len(h_c))
    _, _, h_hx = isobaric_path(T2, T2p, P_high, fluid)           # Hot HX
    P_hx       = np.full(len(h_hx), P_high)
    _, _, h_t  = linear_path(0, 0, T2p, T3,  h2p, h3)           # 터빈
    P_t        = np.linspace(P_high, P_low, len(h_t))
    _, _, h_cx = isobaric_path(T3, T1,  P_low,  fluid)           # Cold HX
    P_cx       = np.full(len(h_cx), P_low)

    fig, ax = plt.subplots(figsize=(7, 5))

    ax.semilogy(h_c  / 1e3, P_c  / 1e3, "b-",  lw=1.8, label="Compressor (1→2)")
    ax.semilogy(h_hx / 1e3, P_hx / 1e3, "r-",  lw=1.8, label="Hot HX (2→2')")
    ax.semilogy(h_t  / 1e3, P_t  / 1e3, "g-",  lw=1.8, label="Turbine (2'→3)")
    ax.semilogy(h_cx / 1e3, P_cx / 1e3, "m-",  lw=1.8, label="Cold HX (3→1)")

    # 상태점 마커
    states_h = [h1, h2, h2p, h3]
    states_P = [P_low, P_high, P_high, P_low]
    labels   = ["1", "2", "2'", "3"]
    ax.scatter([h / 1e3 for h in states_h],
               [P / 1e3 for P in states_P],
               color="k", zorder=5, s=50)
    offsets = [(-18, 5), (4, 4), (4, -12), (-18, -12)]
    for lbl, hx, Px, off in zip(labels, states_h, states_P, offsets):
        ax.annotate(lbl, (hx / 1e3, Px / 1e3),
                    xytext=off, textcoords="offset points", fontsize=10, fontweight="bold")

    ax.set_xlabel("Enthalpy  h  [kJ/kg]",  fontsize=11)
    ax.set_ylabel("Pressure  P  [kPa]  (log scale)", fontsize=11)
    ax.set_title(f"P-h Diagram  |  Air  |  r_p = {out['pressure_ratio']:.2f}  |  COP = {out['COP']:.3f}",
                 fontsize=11)
    ax.legend(fontsize=9, loc="upper left")
    ax.grid(True, alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"    cycle_Ph.png  saved")


# ─────────────────────────────────────────────
# 압력비 파라미터 스윕
# ─────────────────────────────────────────────

def sweep_rp(cfg_base: dict, save_dir: str,
             rp_min: float = 2.0, rp_max: float = 25.0, N: int = 60) -> None:
    rp_vals, cop_vals, qc_vals, T3_vals = [], [], [], []

    for rp in np.linspace(rp_min, rp_max, N):
        cfg = copy.deepcopy(cfg_base)
        cfg["pressure_ratio"] = float(rp)
        try:
            out = solve(cfg)
            rp_vals.append(rp)
            cop_vals.append(out["COP"])
            qc_vals.append(out["Q_cold"] / 1e3)           # kW
            T3_vals.append(out["states"][3].T_celsius())
        except Exception:
            pass   # 범위 밖 r_p 는 스킵

    # CSV 저장
    csv_path = os.path.join(save_dir, "cop_vs_rp.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pressure_ratio", "COP", "Q_cold_kW", "T3_degC"])
        for rp, cop, qc, T3 in zip(rp_vals, cop_vals, qc_vals, T3_vals):
            w.writerow([f"{rp:.4f}", f"{cop:.6f}", f"{qc:.4f}", f"{T3:.4f}"])

    # 플롯
    fig, axes = plt.subplots(1, 3, figsize=(13, 4))

    axes[0].plot(rp_vals, cop_vals, "b-", lw=1.8)
    axes[0].set_xlabel("Pressure Ratio  r_p  [-]", fontsize=10)
    axes[0].set_ylabel("COP", fontsize=10)
    axes[0].set_title("COP vs Pressure Ratio", fontsize=10)
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(rp_vals, qc_vals, "r-", lw=1.8)
    axes[1].set_xlabel("Pressure Ratio  r_p  [-]", fontsize=10)
    axes[1].set_ylabel("Q_cold  [kW]", fontsize=10)
    axes[1].set_title("Refrigeration Capacity vs r_p", fontsize=10)
    axes[1].grid(True, alpha=0.3)

    axes[2].plot(rp_vals, T3_vals, "g-", lw=1.8)
    axes[2].axhline(-100, color="gray", ls="--", lw=1, label="T = -100°C")
    axes[2].set_xlabel("Pressure Ratio  r_p  [-]", fontsize=10)
    axes[2].set_ylabel("Turbine Outlet T  [°C]", fontsize=10)
    axes[2].set_title("T₃ vs Pressure Ratio", fontsize=10)
    axes[2].legend(fontsize=8)
    axes[2].grid(True, alpha=0.3)

    # 목표 r_p 마커 (T3 = -100°C 달성 지점)
    target_rp = None
    for rp, T3 in zip(rp_vals, T3_vals):
        if T3 <= -100.0:
            target_rp = rp
            break
    if target_rp is not None:
        for ax in axes:
            ax.axvline(target_rp, color="orange", ls="--", lw=1.2, label=f"r_p={target_rp:.1f} (T₃=-100°C)")
        for ax in axes:
            ax.legend(fontsize=8)

    fig.suptitle(f"Air Simple Reverse Brayton  |  η_c={cfg_base['eta_compressor']}  η_t={cfg_base['eta_turbine']}",
                 fontsize=11)
    fig.tight_layout()
    png_path = os.path.join(save_dir, "cop_vs_rp.png")
    fig.savefig(png_path, dpi=150)
    plt.close(fig)
    print(f"    cop_vs_rp.png saved")
    print(f"    cop_vs_rp.csv saved")


# ─────────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    args = p.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # 기준점 실행 (pressure_ratio=null → 역산)
    cfg_run = copy.deepcopy(cfg)
    out = solve(cfg_run)

    result_dir = out["result_dir"]
    os.makedirs(result_dir, exist_ok=True)

    print(f"\n  Generating plots → {result_dir}/")
    plot_Ts(out, cfg_run, os.path.join(result_dir, "cycle_Ts.png"))
    plot_Ph(out, cfg_run, os.path.join(result_dir, "cycle_Ph.png"))

    # 파라미터 스윕 (T_compressor_inlet, T_turbine_inlet 고정, r_p 변화)
    print(f"  Running r_p sweep ...")
    sweep_rp(cfg, result_dir)
    print("  Done.")


if __name__ == "__main__":
    main()
