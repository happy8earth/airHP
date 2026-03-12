"""
visualize.py
────────────
사용법:
  python visualize.py --config configs/simple_baseline.yaml
  python visualize.py --config configs/recuperated_baseline.yaml
  python visualize.py --config configs/bypass_a_baseline.yaml

생성 파일:
  results/{run}/cycle_Ts.png         T-s 선도  (simple / recuperated)
  results/{run}/cycle_Ph.png         P-h 선도  (simple / recuperated)
  results/{run}/cop_vs_rp.png        압력비 파라미터 스윕  (simple / recuperated)
  results/{run}/cop_vs_rp.csv
  results/{run}/x_vs_T_sec_out.png   bypass 분율 × T_sec_out_target 스윕  (bypass)
  results/{run}/x_vs_T_sec_out.csv
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
from bypass_solver import solve as bypass_solve
import CoolProp.CoolProp as CP


_BYPASS_CYCLES = {"bypass_a_brayton"}

_CYCLE_MENU = {
    "1": ("Simple Brayton",      "configs/simple_baseline.yaml"),
    "2": ("Recuperated Brayton", "configs/recuperated_baseline.yaml"),
    "3": ("Bypass-A Brayton",    "configs/bypass_a_baseline.yaml"),
}


def _select_config_interactively() -> str:
    """--config 생략 시 사이클 선택 메뉴 표시."""
    print("사이클 선택:")
    for key, (name, path) in _CYCLE_MENU.items():
        print(f"  {key}. {name}  ({path})")
    choice = input("번호 입력 [1]: ").strip() or "1"
    if choice not in _CYCLE_MENU:
        print(f"잘못된 입력 '{choice}' → 1번으로 실행합니다.")
        choice = "1"
    name, path = _CYCLE_MENU[choice]
    print(f"  → {name}  ({path})\n")
    return path


# ─────────────────────────────────────────────
# T_sec_out_target 스윕 (bypass 사이클 전용)
# ─────────────────────────────────────────────

def sweep_T_sec_out(cfg_base: dict, save_dir: str,
                    T_min_K: float = None, T_max_K: float = None,
                    N: int = 30) -> None:
    """
    T_sec_out_target 을 스윕하며 x_bypass, COP, W_net, T_expander_outlet 변화 플롯.

    Parameters
    ----------
    cfg_base  : dict   기준 YAML 설정 (bypass_a_brayton 계열)
    save_dir  : str    결과 저장 폴더
    T_min_K   : float  스윕 하한 [K]  (None → T_sec_in - 10 K)
    T_max_K   : float  스윕 상한 [K]  (None → T_sec_in - 0.5 K)
    N         : int    스윕 포인트 수
    """
    T_sec_in = cfg_base["hx_load"]["hotside"]["T_inlet"]   # IM-7 입구온도 [K]
    if T_max_K is None:
        T_max_K = T_sec_in - 0.5
    if T_min_K is None:
        T_min_K = T_sec_in - 10.0

    T_targets_K = np.linspace(T_min_K, T_max_K, N)

    T_out_C_vals, x_vals, cop_vals, wnet_vals, Tt_vals = [], [], [], [], []

    for T_tgt in T_targets_K:
        cfg = copy.deepcopy(cfg_base)
        cfg["hx_load"]["T_sec_out_target"] = float(T_tgt)
        try:
            out = bypass_solve(cfg)
            T_out_C_vals.append(T_tgt - 273.15)
            x_vals.append(out["x_bypass"])
            cop_vals.append(out["COP"])
            wnet_vals.append(out["W_net"] / 1e3)             # kW
            Tt_vals.append(out["T_expander_outlet"] - 273.15)  # °C
        except Exception:
            pass   # 수렴 불가 포인트 스킵

    if not x_vals:
        print("  sweep_T_sec_out: 수렴 결과 없음, 스킵.")
        return

    # CSV 저장
    csv_path = os.path.join(save_dir, "x_vs_T_sec_out.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["T_sec_out_target_K", "T_sec_out_target_degC",
                    "x_bypass", "COP", "W_net_kW", "T_expander_out_degC"])
        for T_C, x, cop, wnet, Tt in zip(T_out_C_vals, x_vals, cop_vals, wnet_vals, Tt_vals):
            w.writerow([f"{T_C + 273.15:.4f}", f"{T_C:.4f}",
                        f"{x:.6f}", f"{cop:.6f}", f"{wnet:.4f}", f"{Tt:.4f}"])

    # 플롯 (2×2)
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))

    axes[0, 0].plot(T_out_C_vals, x_vals, "b-o", lw=1.8, ms=4)
    axes[0, 0].set_xlabel("T_sec_out_target  [°C]", fontsize=10)
    axes[0, 0].set_ylabel("Bypass Fraction  x  [-]", fontsize=10)
    axes[0, 0].set_title("Bypass Fraction vs T_sec_out_target", fontsize=10)
    axes[0, 0].grid(True, alpha=0.3)

    axes[0, 1].plot(T_out_C_vals, cop_vals, "r-o", lw=1.8, ms=4)
    axes[0, 1].set_xlabel("T_sec_out_target  [°C]", fontsize=10)
    axes[0, 1].set_ylabel("COP  [-]", fontsize=10)
    axes[0, 1].set_title("COP vs T_sec_out_target", fontsize=10)
    axes[0, 1].grid(True, alpha=0.3)

    axes[1, 0].plot(T_out_C_vals, wnet_vals, "g-o", lw=1.8, ms=4)
    axes[1, 0].set_xlabel("T_sec_out_target  [°C]", fontsize=10)
    axes[1, 0].set_ylabel("W_net  [kW]", fontsize=10)
    axes[1, 0].set_title("Net Work vs T_sec_out_target", fontsize=10)
    axes[1, 0].grid(True, alpha=0.3)

    axes[1, 1].plot(T_out_C_vals, Tt_vals, "m-o", lw=1.8, ms=4)
    axes[1, 1].set_xlabel("T_sec_out_target  [°C]", fontsize=10)
    axes[1, 1].set_ylabel("T_expander_outlet  [°C]", fontsize=10)
    axes[1, 1].set_title("Expander Outlet T vs T_sec_out_target", fontsize=10)
    axes[1, 1].grid(True, alpha=0.3)

    # 기준점 (config 기본값) 수직선 마커
    T_tgt_base = cfg_base["hx_load"].get("T_sec_out_target")
    if T_tgt_base is not None:
        T_tgt_base_C = T_tgt_base - 273.15
        for ax in axes.flat:
            ax.axvline(T_tgt_base_C, color="orange", ls="--", lw=1.2,
                       label=f"baseline  {T_tgt_base_C:.1f}°C")
            ax.legend(fontsize=8)

    cycle_name = cfg_base.get("cycle", "bypass_a_brayton")
    fig.suptitle(
        f"{cycle_name}  |  η_c={cfg_base['comp']['eta_isen']}"
        f"  η_t={cfg_base['expander']['eta_isen']}"
        f"  r_p={cfg_base['pressure_ratio']:.2f}",
        fontsize=11)
    fig.tight_layout()
    png_path = os.path.join(save_dir, "x_vs_T_sec_out.png")
    fig.savefig(png_path, dpi=150)
    plt.close(fig)
    print(f"    x_vs_T_sec_out.png saved")
    print(f"    x_vs_T_sec_out.csv saved")


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
    """압축기/팽창기 (비등엔트로피) 선형 경로."""
    s = np.linspace(s1, s2, N)
    T = np.linspace(T1, T2, N)
    h = np.linspace(h1, h2, N)
    return T, s, h


def _annotate_states(ax, states_s, states_T, offsets, labels=None):
    """상태점 번호 주석 (labels 미지정 시 1-based 정수)."""
    ax.scatter([s / 1e3 for s in states_s],
               [T - 273.15 for T in states_T],
               color="k", zorder=5, s=50)
    for i, (sx, Tx, off) in enumerate(zip(states_s, states_T, offsets), start=1):
        lbl = labels[i - 1] if labels else str(i)
        ax.annotate(lbl, (sx / 1e3, Tx - 273.15),
                    xytext=off, textcoords="offset points",
                    fontsize=10, fontweight="bold")


def _annotate_states_Ph(ax, states_h, states_P, offsets, labels=None):
    """P-h 선도 상태점 번호 주석 (labels 미지정 시 1-based 정수)."""
    ax.scatter([h / 1e3 for h in states_h],
               [P / 1e3 for P in states_P],
               color="k", zorder=5, s=50)
    for i, (hx, Px, off) in enumerate(zip(states_h, states_P, offsets), start=1):
        lbl = labels[i - 1] if labels else str(i)
        ax.annotate(lbl, (hx / 1e3, Px / 1e3),
                    xytext=off, textcoords="offset points",
                    fontsize=10, fontweight="bold")


# ─────────────────────────────────────────────
# T-s 선도
# ─────────────────────────────────────────────

def _plot_Ts_simple(ax, out: dict, cfg: dict) -> None:
    """Simple Brayton (4 상태) T-s 선도 경로."""
    fluid  = cfg["fluid"]
    P_low  = cfg["P_low"]
    P_high = out["P_high"]
    s1, s2, s3, s4 = [st.s for st in out["states"]]
    T1, T2, T3, T4 = [st.T for st in out["states"]]

    T_c,  s_c,  _ = linear_path(s1, s2, T1, T2, 0, 0)    # 압축기
    T_hx, s_hx, _ = isobaric_path(T2, T3, P_high, fluid)  # Hot HX
    T_t,  s_t,  _ = linear_path(s3, s4, T3, T4, 0, 0)    # 팽창기
    T_cx, s_cx, _ = isobaric_path(T4, T1, P_low,  fluid)  # Cold HX

    ax.plot(s_c  / 1e3, T_c  - 273.15, "b-", lw=1.8, label="Compressor (1→2)")
    ax.plot(s_hx / 1e3, T_hx - 273.15, "r-", lw=1.8, label="Hot HX (2→3)")
    ax.plot(s_t  / 1e3, T_t  - 273.15, "g-", lw=1.8, label="Expander (3→4)")
    ax.plot(s_cx / 1e3, T_cx - 273.15, "m-", lw=1.8, label="Cold HX (4→1)")

    offsets = [(-18, 5), (5, 5), (5, 5), (5, -12)]
    _annotate_states(ax, [s1, s2, s3, s4], [T1, T2, T3, T4], offsets)


def _plot_Ts_recuperated(ax, out: dict, cfg: dict) -> None:
    """Recuperated Brayton (6 상태) T-s 선도 경로."""
    fluid  = cfg["fluid"]
    P_low  = cfg["P_low"]
    P_high = out["P_high"]
    s1, s2, s3, s4, s5, s6 = [st.s for st in out["states"]]
    T1, T2, T3, T4, T5, T6 = [st.T for st in out["states"]]

    T_c,   s_c,   _ = linear_path(s1, s2, T1, T2, 0, 0)     # 압축기
    T_hx,  s_hx,  _ = isobaric_path(T2, T3, P_high, fluid)   # Hot HX
    T_rh,  s_rh,  _ = isobaric_path(T3, T4, P_high, fluid)   # Recuperator hot
    T_t,   s_t,   _ = linear_path(s4, s5, T4, T5, 0, 0)     # 팽창기
    T_cx,  s_cx,  _ = isobaric_path(T5, T6, P_low,  fluid)   # Cold HX
    T_rc,  s_rc,  _ = isobaric_path(T6, T1, P_low,  fluid)   # Recuperator cold

    ax.plot(s_c  / 1e3, T_c  - 273.15, "b-",                 lw=1.8, label="Compressor (1→2)")
    ax.plot(s_hx / 1e3, T_hx - 273.15, "r-",                 lw=1.8, label="Hot HX (2→3)")
    ax.plot(s_rh / 1e3, T_rh - 273.15, color="darkorange",   lw=1.8, label="Recup hot (3→4)", ls="--")
    ax.plot(s_t  / 1e3, T_t  - 273.15, "g-",                 lw=1.8, label="Expander (4→5)")
    ax.plot(s_cx / 1e3, T_cx - 273.15, "m-",                 lw=1.8, label="Cold HX (5→6)")
    ax.plot(s_rc / 1e3, T_rc - 273.15, color="mediumpurple", lw=1.8, label="Recup cold (6→1)", ls="--")

    offsets = [(-18, 5), (5, 5), (5, 5), (5, 5), (5, -12), (-18, 5)]
    _annotate_states(ax, [s1, s2, s3, s4, s5, s6], [T1, T2, T3, T4, T5, T6], offsets)


def _plot_Ts_bypass_a(ax, out: dict, cfg: dict) -> None:
    """Bypass-A Brayton (7 상태) T-s 선도 경로.

    states 순서: [1, 2, 3, 4, 4m, 5, 6]
    """
    fluid  = cfg["fluid"]
    P_low  = cfg["P_low"]
    P_high = out["P_high"]
    s_arr = [st.s for st in out["states"]]
    T_arr = [st.T for st in out["states"]]
    s1, s2, _, s4, s4m, s5, _ = s_arr
    T1, T2, T3, T4, T4m, T5, T6 = T_arr

    T_c,  s_c,  _ = linear_path(s1,  s2,  T1,  T2,  0, 0)    # 1→2 Compressor
    T_hx, s_hx, _ = isobaric_path(T2, T3, P_high, fluid)      # 2→3 Aftercooler
    T_rh, s_rh, _ = isobaric_path(T3, T4, P_high, fluid)      # 3→4 Recup hot
    T_t,  s_t,  _ = linear_path(s4m, s5, T4m, T5, 0, 0)      # 4m→5 Expander
    T_cx, s_cx, _ = isobaric_path(T5, T6, P_low,  fluid)      # 5→6 Load HX
    T_rc, s_rc, _ = isobaric_path(T6, T1, P_low,  fluid)      # 6→1 Recup cold

    ax.plot(s_c  / 1e3, T_c  - 273.15, "b-",                 lw=1.8, label="Compressor (1→2)")
    ax.plot(s_hx / 1e3, T_hx - 273.15, "r-",                 lw=1.8, label="Aftercooler (2→3)")
    ax.plot(s_rh / 1e3, T_rh - 273.15, color="darkorange",   lw=1.8, label="Recup hot (3→4)", ls="--")
    # Bypass stream: State2 → Mixer (conceptual path to 4m)
    ax.plot([s2 / 1e3, s4m / 1e3], [T2 - 273.15, T4m - 273.15],
            color="gray", lw=1.2, ls=":", label=f"Bypass (2→4m, x={out.get('x_bypass', 0):.3f})")
    # Recup hot out → Mixer (4→4m)
    ax.plot([s4 / 1e3, s4m / 1e3], [T4 - 273.15, T4m - 273.15],
            color="gray", lw=1.2, ls="--", label="Mixer (4→4m)")
    ax.plot(s_t  / 1e3, T_t  - 273.15, "g-",                 lw=1.8, label="Expander (4m→5)")
    ax.plot(s_cx / 1e3, T_cx - 273.15, "m-",                 lw=1.8, label="Load HX (5→6)")
    ax.plot(s_rc / 1e3, T_rc - 273.15, color="mediumpurple", lw=1.8, label="Recup cold (6→1)", ls="--")

    offsets = [(-18, 5), (5, 5), (5, 5), (5, -12), (5, 5), (5, -12), (-18, 5)]
    _annotate_states(ax, s_arr, T_arr, offsets,
                     labels=["1", "2", "3", "4", "4m", "5", "6"])


def plot_Ts(out: dict, cfg: dict, save_path: str) -> None:
    fig, ax = plt.subplots(figsize=(7, 5))

    if out["cycle"] == "bypass_a_brayton":
        _plot_Ts_bypass_a(ax, out, cfg)
    elif out["cycle"] == "recuperated_brayton":
        _plot_Ts_recuperated(ax, out, cfg)
    else:
        _plot_Ts_simple(ax, out, cfg)

    ax.axhline(0,    color="gray", lw=0.6, ls="--")
    ax.axhline(-100, color="gray", lw=0.6, ls="--")
    ax.set_xlabel("Entropy  s  [kJ/(kg·K)]", fontsize=11)
    ax.set_ylabel("Temperature  T  [°C]",    fontsize=11)
    ax.set_title(
        f"T-s Diagram  |  {cfg['fluid']}  |  {out['cycle']}"
        f"  |  r_p = {out['pressure_ratio']:.2f}  |  COP = {out['COP']:.3f}",
        fontsize=10)
    ax.legend(fontsize=9, loc="upper left")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(save_path, dpi=150)
    plt.close(fig)
    print(f"    cycle_Ts.png  saved")


# ─────────────────────────────────────────────
# P-h 선도
# ─────────────────────────────────────────────

def _plot_Ph_simple(ax, out: dict, cfg: dict) -> None:
    """Simple Brayton (4 상태) P-h 선도 경로."""
    fluid  = cfg["fluid"]
    P_low  = cfg["P_low"]
    P_high = out["P_high"]
    h1, h2, h3, h4 = [st.h for st in out["states"]]
    T1, T2, T3, T4 = [st.T for st in out["states"]]

    _, _, h_c  = linear_path(0, 0, T1, T2, h1, h2)
    P_c        = np.linspace(P_low, P_high, len(h_c))
    _, _, h_hx = isobaric_path(T2, T3, P_high, fluid)
    P_hx       = np.full(len(h_hx), P_high)
    _, _, h_t  = linear_path(0, 0, T3, T4, h3, h4)
    P_t        = np.linspace(P_high, P_low, len(h_t))
    _, _, h_cx = isobaric_path(T4, T1, P_low,  fluid)
    P_cx       = np.full(len(h_cx), P_low)

    ax.semilogy(h_c  / 1e3, P_c  / 1e3, "b-", lw=1.8, label="Compressor (1→2)")
    ax.semilogy(h_hx / 1e3, P_hx / 1e3, "r-", lw=1.8, label="Hot HX (2→3)")
    ax.semilogy(h_t  / 1e3, P_t  / 1e3, "g-", lw=1.8, label="Expander (3→4)")
    ax.semilogy(h_cx / 1e3, P_cx / 1e3, "m-", lw=1.8, label="Cold HX (4→1)")

    offsets  = [(-18, 5), (4, 4), (4, -12), (-18, -12)]
    states_P = [P_low, P_high, P_high, P_low]
    _annotate_states_Ph(ax, [h1, h2, h3, h4], states_P, offsets)


def _plot_Ph_recuperated(ax, out: dict, cfg: dict) -> None:
    """Recuperated Brayton (6 상태) P-h 선도 경로."""
    fluid  = cfg["fluid"]
    P_low  = cfg["P_low"]
    P_high = out["P_high"]
    h1, h2, h3, h4, h5, h6 = [st.h for st in out["states"]]
    T1, T2, T3, T4, T5, T6 = [st.T for st in out["states"]]

    _, _, h_c  = linear_path(0, 0, T1, T2, h1, h2)
    P_c        = np.linspace(P_low, P_high, len(h_c))
    _, _, h_hx = isobaric_path(T2, T3, P_high, fluid)
    P_hx       = np.full(len(h_hx), P_high)
    _, _, h_rh = isobaric_path(T3, T4, P_high, fluid)
    P_rh       = np.full(len(h_rh), P_high)
    _, _, h_t  = linear_path(0, 0, T4, T5, h4, h5)
    P_t        = np.linspace(P_high, P_low, len(h_t))
    _, _, h_cx = isobaric_path(T5, T6, P_low,  fluid)
    P_cx       = np.full(len(h_cx), P_low)
    _, _, h_rc = isobaric_path(T6, T1, P_low,  fluid)
    P_rc       = np.full(len(h_rc), P_low)

    ax.semilogy(h_c  / 1e3, P_c  / 1e3, "b-",                 lw=1.8, label="Compressor (1→2)")
    ax.semilogy(h_hx / 1e3, P_hx / 1e3, "r-",                 lw=1.8, label="Hot HX (2→3)")
    ax.semilogy(h_rh / 1e3, P_rh / 1e3, color="darkorange",   lw=1.8, label="Recup hot (3→4)", ls="--")
    ax.semilogy(h_t  / 1e3, P_t  / 1e3, "g-",                 lw=1.8, label="Expander (4→5)")
    ax.semilogy(h_cx / 1e3, P_cx / 1e3, "m-",                 lw=1.8, label="Cold HX (5→6)")
    ax.semilogy(h_rc / 1e3, P_rc / 1e3, color="mediumpurple", lw=1.8, label="Recup cold (6→1)", ls="--")

    offsets  = [(-18, 5), (4, 4), (4, 4), (4, -12), (-18, -12), (-18, 5)]
    states_P = [P_low, P_high, P_high, P_high, P_low, P_low]
    _annotate_states_Ph(ax, [h1, h2, h3, h4, h5, h6], states_P, offsets)


def _plot_Ph_bypass_a(ax, out: dict, cfg: dict) -> None:
    """Bypass-A Brayton (7 상태) P-h 선도 경로.

    states 순서: [1, 2, 3, 4, 4m, 5, 6]
    """
    fluid  = cfg["fluid"]
    P_low  = cfg["P_low"]
    P_high = out["P_high"]
    h_arr = [st.h for st in out["states"]]
    T_arr = [st.T for st in out["states"]]
    h1, h2, _, h4, h4m, h5, _ = h_arr
    T1, T2, T3, T4, T4m, T5, T6 = T_arr

    _, _, h_c  = linear_path(0, 0, T1,  T2,  h1,  h2)
    P_c        = np.linspace(P_low,  P_high, len(h_c))
    _, _, h_hx = isobaric_path(T2, T3, P_high, fluid)
    P_hx       = np.full(len(h_hx), P_high)
    _, _, h_rh = isobaric_path(T3, T4, P_high, fluid)
    P_rh       = np.full(len(h_rh), P_high)
    _, _, h_t  = linear_path(0, 0, T4m, T5,  h4m, h5)
    P_t        = np.linspace(P_high, P_low,  len(h_t))
    _, _, h_cx = isobaric_path(T5, T6, P_low,  fluid)
    P_cx       = np.full(len(h_cx), P_low)
    _, _, h_rc = isobaric_path(T6, T1, P_low,  fluid)
    P_rc       = np.full(len(h_rc), P_low)

    ax.semilogy(h_c  / 1e3, P_c  / 1e3, "b-",                 lw=1.8, label="Compressor (1→2)")
    ax.semilogy(h_hx / 1e3, P_hx / 1e3, "r-",                 lw=1.8, label="Aftercooler (2→3)")
    ax.semilogy(h_rh / 1e3, P_rh / 1e3, color="darkorange",   lw=1.8, label="Recup hot (3→4)", ls="--")
    # 두 스트림이 P_high에서 혼합: State2(bypass)→4m, State4(main)→4m
    ax.semilogy([h2 / 1e3, h4m / 1e3], [P_high / 1e3] * 2,
                color="gray", lw=1.2, ls=":",  label=f"Bypass (2→4m, x={out.get('x_bypass', 0):.3f})")
    ax.semilogy([h4 / 1e3, h4m / 1e3], [P_high / 1e3] * 2,
                color="gray", lw=1.2, ls="--", label="Mixer (4→4m)")
    ax.semilogy(h_t  / 1e3, P_t  / 1e3, "g-",                 lw=1.8, label="Expander (4m→5)")
    ax.semilogy(h_cx / 1e3, P_cx / 1e3, "m-",                 lw=1.8, label="Load HX (5→6)")
    ax.semilogy(h_rc / 1e3, P_rc / 1e3, color="mediumpurple", lw=1.8, label="Recup cold (6→1)", ls="--")

    offsets  = [(-18, 5), (4, 4), (4, 4), (4, -12), (4, 4), (4, -12), (-18, 5)]
    states_P = [P_low, P_high, P_high, P_high, P_high, P_low, P_low]
    _annotate_states_Ph(ax, h_arr, states_P, offsets,
                        labels=["1", "2", "3", "4", "4m", "5", "6"])


def plot_Ph(out: dict, cfg: dict, save_path: str) -> None:
    fig, ax = plt.subplots(figsize=(7, 5))

    if out["cycle"] == "bypass_a_brayton":
        _plot_Ph_bypass_a(ax, out, cfg)
    elif out["cycle"] == "recuperated_brayton":
        _plot_Ph_recuperated(ax, out, cfg)
    else:
        _plot_Ph_simple(ax, out, cfg)

    ax.set_xlabel("Enthalpy  h  [kJ/kg]",            fontsize=11)
    ax.set_ylabel("Pressure  P  [kPa]  (log scale)", fontsize=11)
    ax.set_title(
        f"P-h Diagram  |  {cfg['fluid']}  |  {out['cycle']}"
        f"  |  r_p = {out['pressure_ratio']:.2f}  |  COP = {out['COP']:.3f}",
        fontsize=10)
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
    rp_vals, cop_vals, qc_vals, Tt_vals = [], [], [], []

    for rp in np.linspace(rp_min, rp_max, N):
        cfg = copy.deepcopy(cfg_base)
        cfg["pressure_ratio"] = float(rp)
        try:
            out = solve(cfg)
            rp_vals.append(rp)
            cop_vals.append(out["COP"])
            qc_vals.append(out["Q_cold"] / 1e3)                  # kW
            Tt_vals.append(out["T_expander_outlet"] - 273.15)     # °C
        except Exception:
            pass   # 범위 밖 r_p 는 스킵

    # CSV 저장
    csv_path = os.path.join(save_dir, "cop_vs_rp.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pressure_ratio", "COP", "Q_cold_kW", "T_expander_out_degC"])
        for rp, cop, qc, Tt in zip(rp_vals, cop_vals, qc_vals, Tt_vals):
            w.writerow([f"{rp:.4f}", f"{cop:.6f}", f"{qc:.4f}", f"{Tt:.4f}"])

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

    axes[2].plot(rp_vals, Tt_vals, "g-", lw=1.8)
    axes[2].axhline(-100, color="gray", ls="--", lw=1, label="T = -100°C")
    axes[2].set_xlabel("Pressure Ratio  r_p  [-]", fontsize=10)
    axes[2].set_ylabel("Expander Outlet T  [°C]", fontsize=10)
    axes[2].set_title("T_expander_out vs Pressure Ratio", fontsize=10)
    axes[2].legend(fontsize=8)
    axes[2].grid(True, alpha=0.3)

    # 목표 r_p 마커 (T_turb_out = -100°C 달성 지점)
    target_rp = None
    for rp, Tt in zip(rp_vals, Tt_vals):
        if Tt <= -100.0:
            target_rp = rp
            break
    if target_rp is not None:
        for ax in axes:
            ax.axvline(target_rp, color="orange", ls="--", lw=1.2,
                       label=f"r_p={target_rp:.1f} (T=-100°C)")
        for ax in axes:
            ax.legend(fontsize=8)

    cycle_name = cfg_base.get("cycle", "simple_brayton")
    recup = cfg_base.get("hx_recup", {})
    eps_str = (f"  ε={recup['effectiveness']}" if "effectiveness" in recup else "")
    fig.suptitle(
        f"{cycle_name}  |  η_c={cfg_base['comp']['eta_isen']}"
        f"  η_t={cfg_base['expander']['eta_isen']}{eps_str}",
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
    p.add_argument("--config", default=None,
                   help="YAML 설정 파일 경로 (생략 시 메뉴 선택)")
    args = p.parse_args()

    config_path = args.config if args.config else _select_config_interactively()

    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    is_bypass = cfg.get("cycle") in _BYPASS_CYCLES

    if is_bypass:
        # ── Bypass 사이클 ──────────────────────────────────
        cfg_run = copy.deepcopy(cfg)
        out = bypass_solve(cfg_run)
        result_dir = out["result_dir"]
        os.makedirs(result_dir, exist_ok=True)

        print(f"\n  Generating plots → {result_dir}/")
        plot_Ts(out, cfg_run, os.path.join(result_dir, "cycle_Ts.png"))
        plot_Ph(out, cfg_run, os.path.join(result_dir, "cycle_Ph.png"))
        print(f"  Running T_sec_out sweep ...")
        sweep_T_sec_out(cfg, result_dir)
        print("  Done.")
    else:
        # ── Simple / Recuperated 사이클 ───────────────────
        cfg_run = copy.deepcopy(cfg)
        out = solve(cfg_run)

        result_dir = out["result_dir"]
        os.makedirs(result_dir, exist_ok=True)

        print(f"\n  Generating plots → {result_dir}/")
        plot_Ts(out, cfg_run, os.path.join(result_dir, "cycle_Ts.png"))
        plot_Ph(out, cfg_run, os.path.join(result_dir, "cycle_Ph.png"))

        print(f"  Running r_p sweep ...")
        sweep_rp(cfg, result_dir)
        print("  Done.")


if __name__ == "__main__":
    main()
