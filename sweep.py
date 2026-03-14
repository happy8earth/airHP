"""
sweep.py
────────
결합 솔버 파라미터 스윕.

사용법:
  python sweep.py --config configs/bypass_a_baseline.yaml --mode Q           # Q_heater 스윕
  python sweep.py --config configs/bypass_a_baseline.yaml --mode T           # T_sec_out_target 스윕
  python sweep.py --config configs/bypass_a_baseline.yaml --mode 2D          # 2D 그리드

스윕 범위 옵션 (모두 선택적):
  --Q_min 100 --Q_max 5000 --Q_n 50           [W]
  --T_min -120 --T_max 25  --T_n 50           [°C]

출력:
  results/sweep_<timestamp>/  ── sweep_results.csv, *.png
"""

import argparse
import copy
import csv
import os
import sys
import time
import yaml

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from coupled_solver import solve as coupled_solve


# ─────────────────────────────────────────────
# 단일 포인트 계산 (실패 시 None)
# ─────────────────────────────────────────────


def _run_point(
    cfg_base: dict, Q_heater: float, T_sec_out_target_K: float
) -> dict | None:
    """하나의 (Q_heater, T_sec_out_target) 조합으로 coupled_solve 실행."""
    cfg = copy.deepcopy(cfg_base)
    cfg["load_side"]["Q_heater"] = float(Q_heater)
    cfg["hx_load"]["T_sec_out_target"] = float(T_sec_out_target_K)
    try:
        out = coupled_solve(cfg)
        return dict(
            Q_heater=Q_heater,
            T_sec_out_target_C=T_sec_out_target_K - 273.15,
            x_bypass=out["x_bypass"],
            y_sec=out["y_sec"],
            mdot_load_sec=out["mdot_load_sec"],
            T_load_sec_in_C=out["T_load_sec_in"] - 273.15,
            T_load_sec_out_C=out["T_load_sec_out"] - 273.15,
            Q_cold=out["Q_cold"],
            W_net=out["W_net"],
            W_heater=Q_heater,  # 히터는 전력 소비 = Q_heater (100% 효율 가정)
            W_total=out["W_net"] + Q_heater,
            COP_net=out["COP"],  # Q_cold / W_net
            COP_total=(
                out["Q_cold"] / (out["W_net"] + Q_heater)
                if (out["W_net"] + Q_heater) > 0
                else float("nan")
            ),
            energy_error=out["energy_error"],
            status="ok",
        )
    except Exception as e:
        return dict(
            Q_heater=Q_heater,
            T_sec_out_target_C=T_sec_out_target_K - 273.15,
            status=f"fail: {e}",
        )


# ─────────────────────────────────────────────
# 스윕 실행
# ─────────────────────────────────────────────


def sweep_Q(cfg: dict, Q_values: np.ndarray, T_target_K: float) -> list[dict]:
    """Q_heater 스윕 (T_sec_out_target 고정)."""
    results = []
    for i, Q in enumerate(Q_values):
        r = _run_point(cfg, Q, T_target_K)
        status = r.get("status", "ok")
        print(f"  [{i+1:3d}/{len(Q_values)}] Q={Q:.0f}W  → {status}", end="\r")
        results.append(r)
    print()
    return results


def sweep_T(cfg: dict, Q_heater: float, T_values_K: np.ndarray) -> list[dict]:
    """T_sec_out_target 스윕 (Q_heater 고정)."""
    results = []
    for i, T in enumerate(T_values_K):
        r = _run_point(cfg, Q_heater, T)
        status = r.get("status", "ok")
        print(
            f"  [{i+1:3d}/{len(T_values_K)}] T={T-273.15:.1f}°C  → {status}", end="\r"
        )
        results.append(r)
    print()
    return results


def sweep_2D(cfg: dict, Q_values: np.ndarray, T_values_K: np.ndarray) -> list[dict]:
    """2D 그리드 스윕."""
    results = []
    total = len(Q_values) * len(T_values_K)
    cnt = 0
    for Q in Q_values:
        for T in T_values_K:
            cnt += 1
            r = _run_point(cfg, Q, T)
            status = r.get("status", "ok")
            print(
                f"  [{cnt:4d}/{total}] Q={Q:.0f}W T={T-273.15:.1f}°C  → {status}",
                end="\r",
            )
            results.append(r)
    print()
    return results


# ─────────────────────────────────────────────
# CSV 저장
# ─────────────────────────────────────────────

_FIELDS = [
    "Q_heater",
    "T_sec_out_target_C",
    "x_bypass",
    "y_sec",
    "mdot_load_sec",
    "T_load_sec_in_C",
    "T_load_sec_out_C",
    "Q_cold",
    "W_net",
    "W_heater",
    "W_total",
    "COP_net",
    "COP_total",
    "energy_error",
    "status",
]


def save_csv(results: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in results:
            w.writerow(r)
    print(f"  CSV 저장: {path}")


# ─────────────────────────────────────────────
# 시각화
# ─────────────────────────────────────────────


def _ok(results: list[dict]) -> list[dict]:
    return [r for r in results if r.get("status") == "ok"]


def plot_Q_sweep(results: list[dict], out_dir: str, T_target_C: float) -> None:
    ok = _ok(results)
    if not ok:
        print("  plot_Q_sweep: 유효 데이터 없음.")
        return

    Q = np.array([r["Q_heater"] for r in ok])
    Wn = np.array([r["W_net"] for r in ok]) / 1e3
    Wh = np.array([r["W_heater"] for r in ok]) / 1e3
    Wt = np.array([r["W_total"] for r in ok]) / 1e3
    x = np.array([r["x_bypass"] for r in ok])
    y = np.array([r["y_sec"] for r in ok])

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle(
        f"Q_heater 스윕  (T_sec_out_target = {T_target_C:.1f} °C)", fontsize=13
    )

    ax = axes[0, 0]
    ax.plot(Q / 1e3, Wt, "k-o", ms=4, label="W_total = W_net + W_heater")
    ax.plot(Q / 1e3, Wn, "b--s", ms=3, label="W_net")
    ax.plot(Q / 1e3, Wh, "r--^", ms=3, label="W_heater (= Q_heater)")
    ax.set_xlabel("Q_heater [kW]")
    ax.set_ylabel("Power [kW]")
    ax.set_title("Total Power vs Q_heater")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    # 최소 W_total 표시
    idx_min = np.argmin(Wt)
    ax.axvline(Q[idx_min] / 1e3, color="k", ls=":", alpha=0.6)
    ax.annotate(
        f"min {Wt[idx_min]:.2f} kW\n@ {Q[idx_min]:.0f} W",
        xy=(Q[idx_min] / 1e3, Wt[idx_min]),
        xytext=(5, 10),
        textcoords="offset points",
        fontsize=8,
        color="k",
    )

    ax = axes[0, 1]
    COPt = np.array([r.get("COP_total", float("nan")) for r in ok])
    ax.plot(Q / 1e3, COPt, "g-o", ms=4)
    ax.set_xlabel("Q_heater [kW]")
    ax.set_ylabel("COP_total = Q_cold / W_total")
    ax.set_title("COP_total vs Q_heater")
    ax.grid(True, alpha=0.3)

    ax = axes[1, 0]
    ax.plot(Q / 1e3, x, "b-o", ms=4, label="x (air bypass)")
    ax.plot(Q / 1e3, y, "r-s", ms=4, label="y (IM-7 bypass)")
    ax.set_xlabel("Q_heater [kW]")
    ax.set_ylabel("Bypass fraction [-]")
    ax.set_title("Bypass Fractions vs Q_heater")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    ax = axes[1, 1]
    T_in = np.array([r.get("T_load_sec_in_C", float("nan")) for r in ok])
    T_out = np.array([r.get("T_load_sec_out_C", float("nan")) for r in ok])
    ax.plot(Q / 1e3, T_in, "r-o", ms=4, label="T_load_sec_in")
    ax.plot(Q / 1e3, T_out, "b--s", ms=4, label="T_load_sec_out (= T_target)")
    ax.axhline(
        results[0].get("T_sec_out_target_C", T_target_C),
        color="gray",
        ls=":",
        alpha=0.7,
        label="T_sec_out_target",
    )
    ax.set_xlabel("Q_heater [kW]")
    ax.set_ylabel("Temperature [°C]")
    ax.set_title("IM-7 Temperatures vs Q_heater")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = os.path.join(out_dir, "sweep_Q_heater.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  그래프 저장: {path}")


def plot_T_sweep(results: list[dict], out_dir: str, Q_heater: float) -> None:
    ok = _ok(results)
    if not ok:
        print("  plot_T_sweep: 유효 데이터 없음.")
        return

    T = np.array([r["T_sec_out_target_C"] for r in ok])
    Wt = np.array([r["W_total"] for r in ok]) / 1e3
    Wn = np.array([r["W_net"] for r in ok]) / 1e3
    x = np.array([r["x_bypass"] for r in ok])
    y = np.array([r["y_sec"] for r in ok])

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle(f"T_sec_out_target 스윕  (Q_heater = {Q_heater:.0f} W)", fontsize=13)

    ax = axes[0, 0]
    ax.plot(T, Wt, "k-o", ms=4, label="W_total")
    ax.plot(T, Wn, "b--s", ms=3, label="W_net")
    ax.set_xlabel("T_sec_out_target [°C]")
    ax.set_ylabel("Power [kW]")
    ax.set_title("Total Power vs T_target")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    idx_min = np.argmin(Wt)
    ax.axvline(T[idx_min], color="k", ls=":", alpha=0.6)
    ax.annotate(
        f"min {Wt[idx_min]:.2f} kW\n@ {T[idx_min]:.1f} °C",
        xy=(T[idx_min], Wt[idx_min]),
        xytext=(5, 10),
        textcoords="offset points",
        fontsize=8,
    )

    ax = axes[0, 1]
    COPt = np.array([r.get("COP_total", float("nan")) for r in ok])
    ax.plot(T, COPt, "g-o", ms=4)
    ax.set_xlabel("T_sec_out_target [°C]")
    ax.set_ylabel("COP_total")
    ax.set_title("COP_total vs T_target")
    ax.grid(True, alpha=0.3)

    ax = axes[1, 0]
    ax.plot(T, x, "b-o", ms=4, label="x (air bypass)")
    ax.plot(T, y, "r-s", ms=4, label="y (IM-7 bypass)")
    ax.set_xlabel("T_sec_out_target [°C]")
    ax.set_ylabel("Bypass fraction [-]")
    ax.set_title("Bypass Fractions vs T_target")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)

    ax = axes[1, 1]
    mdot = np.array([r.get("mdot_load_sec", float("nan")) for r in ok])
    ax.plot(T, mdot, "m-o", ms=4)
    ax.set_xlabel("T_sec_out_target [°C]")
    ax.set_ylabel("m_dot_load_sec [kg/s]")
    ax.set_title("IM-7 Flow through LoadHX vs T_target")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    path = os.path.join(out_dir, "sweep_T_target.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  그래프 저장: {path}")


def plot_2D(
    results: list[dict], out_dir: str, Q_values: np.ndarray, T_values_K: np.ndarray
) -> None:
    """W_total 2D 히트맵."""
    nQ = len(Q_values)
    nT = len(T_values_K)
    W_total = np.full((nQ, nT), np.nan)

    for r in results:
        if r.get("status") != "ok":
            continue
        # Q 인덱스, T 인덱스 역산
        Q_arr = Q_values
        T_arr = T_values_K - 273.15
        q_idx = np.argmin(np.abs(Q_arr - r["Q_heater"]))
        t_idx = np.argmin(np.abs(T_arr - r["T_sec_out_target_C"]))
        W_total[q_idx, t_idx] = r["W_total"] / 1e3

    fig, ax = plt.subplots(figsize=(10, 7))
    T_C = T_values_K - 273.15
    img = ax.pcolormesh(T_C, Q_values / 1e3, W_total, cmap="RdYlGn_r", shading="auto")
    plt.colorbar(img, ax=ax, label="W_total = W_net + W_heater [kW]")
    ax.set_xlabel("T_sec_out_target [°C]")
    ax.set_ylabel("Q_heater [kW]")
    ax.set_title("W_total 2D 히트맵  (역브레이튼 부하측 결합)")

    # 최소 W_total 위치 표시
    valid = ~np.isnan(W_total)
    if valid.any():
        idx = np.unravel_index(np.nanargmin(W_total), W_total.shape)
        ax.plot(
            T_C[idx[1]],
            Q_values[idx[0]] / 1e3,
            "w*",
            ms=15,
            label=f"min {W_total[idx]:.2f} kW\n(T={T_C[idx[1]]:.1f}°C, Q={Q_values[idx[0]]:.0f}W)",
        )
        ax.legend(fontsize=9)

    plt.tight_layout()
    path = os.path.join(out_dir, "sweep_2D_W_total.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  그래프 저장: {path}")


# ─────────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────────


def main():
    p = argparse.ArgumentParser(description="Coupled solver parameter sweep")
    p.add_argument("--config", default="configs/bypass_a_baseline.yaml")
    p.add_argument(
        "--mode",
        default="Q",
        choices=["Q", "T", "2D"],
        help="스윕 모드: Q=Q_heater 스윕, T=T_target 스윕, 2D=2D 그리드",
    )
    p.add_argument("--Q_min", type=float, default=100.0, help="Q_heater 최솟값 [W]")
    p.add_argument("--Q_max", type=float, default=5000.0, help="Q_heater 최댓값 [W]")
    p.add_argument("--Q_n", type=int, default=20, help="Q_heater 분할 수")
    p.add_argument(
        "--T_min", type=float, default=-120.0, help="T_sec_out_target 최솟값 [°C]"
    )
    p.add_argument(
        "--T_max", type=float, default=25.0, help="T_sec_out_target 최댓값 [°C]"
    )
    p.add_argument("--T_n", type=int, default=20, help="T_sec_out_target 분할 수")
    args = p.parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # 스윕 범위
    Q_values = np.linspace(args.Q_min, args.Q_max, args.Q_n)
    T_values_K = np.linspace(args.T_min + 273.15, args.T_max + 273.15, args.T_n)

    # T_max은 T_chuck_sec_in 미만이어야 함
    T_chuck = cfg["load_side"]["T_chuck_sec_in"]
    T_values_K = T_values_K[T_values_K < T_chuck - 0.5]  # 0.5K 마진

    # 결과 저장 폴더
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join("results", f"sweep_{args.mode}_{ts}")
    os.makedirs(out_dir, exist_ok=True)
    print(f"저장 폴더: {out_dir}")

    # YAML 기본값 (고정값으로 사용)
    Q_fixed = cfg["load_side"]["Q_heater"]
    T_fixed_K = cfg["hx_load"]["T_sec_out_target"]

    # ── 스윕 실행 ───────────────────────────────────────────────────────────
    if args.mode == "Q":
        print(
            f"\nQ_heater 스윕  ({len(Q_values)}포인트,  T_target={T_fixed_K-273.15:.1f}°C 고정)"
        )
        results = sweep_Q(cfg, Q_values, T_fixed_K)
        save_csv(results, os.path.join(out_dir, "sweep_results.csv"))
        plot_Q_sweep(results, out_dir, T_fixed_K - 273.15)

    elif args.mode == "T":
        print(
            f"\nT_sec_out_target 스윕  ({len(T_values_K)}포인트,  Q_heater={Q_fixed:.0f}W 고정)"
        )
        results = sweep_T(cfg, Q_fixed, T_values_K)
        save_csv(results, os.path.join(out_dir, "sweep_results.csv"))
        plot_T_sweep(results, out_dir, Q_fixed)

    elif args.mode == "2D":
        print(
            f"\n2D 그리드 스윕  ({len(Q_values)} × {len(T_values_K)} = "
            f"{len(Q_values)*len(T_values_K)}포인트)"
        )
        results = sweep_2D(cfg, Q_values, T_values_K)
        save_csv(results, os.path.join(out_dir, "sweep_results.csv"))
        plot_2D(results, out_dir, Q_values, T_values_K)
        # 각 축에 대한 1D 슬라이스도 저장
        Q_mid_idx = len(Q_values) // 2
        T_mid_idx = len(T_values_K) // 2
        ok_2d = [r for r in results if r.get("status") == "ok"]
        slice_Q = [
            r
            for r in ok_2d
            if abs(r["T_sec_out_target_C"] - (T_values_K[T_mid_idx] - 273.15)) < 2.0
        ]
        slice_T = [
            r
            for r in ok_2d
            if abs(r["Q_heater"] - Q_values[Q_mid_idx])
            < (args.Q_max - args.Q_min) / args.Q_n
        ]
        if slice_Q:
            plot_Q_sweep(slice_Q, out_dir, T_values_K[T_mid_idx] - 273.15)
        if slice_T:
            plot_T_sweep(slice_T, out_dir, Q_values[Q_mid_idx])

    # 요약 출력
    ok_results = _ok(results)
    fail_cnt = len(results) - len(ok_results)
    print(f"\n완료: {len(ok_results)}/{len(results)} 성공, {fail_cnt} 실패")
    if ok_results:
        W_vals = [r["W_total"] for r in ok_results]
        idx_min = int(np.argmin(W_vals))
        r_opt = ok_results[idx_min]
        print(f"최적 운전점 (W_total 최소):")
        print(f"  Q_heater          = {r_opt['Q_heater']:.1f} W")
        print(f"  T_sec_out_target  = {r_opt['T_sec_out_target_C']:.2f} °C")
        print(f"  x_bypass          = {r_opt.get('x_bypass', float('nan')):.4f}")
        print(f"  y_sec             = {r_opt.get('y_sec', float('nan')):.4f}")
        print(f"  W_net             = {r_opt.get('W_net', float('nan'))/1e3:.3f} kW")
        print(f"  W_total           = {r_opt['W_total']/1e3:.3f} kW")
        print(f"  COP_total         = {r_opt.get('COP_total', float('nan')):.4f}")


if __name__ == "__main__":
    main()
