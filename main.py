"""
main.py
───────
사용법:
  python main.py --config configs/simple_baseline.yaml
"""

import argparse
import os
import sys
import yaml
import csv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from cycle_solver import solve


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Simple Reverse Brayton Cryogenic Refrigerator")
    p.add_argument("--config", required=True, help="YAML 설정 파일 경로")
    return p.parse_args()


# ─────────────────────────────────────────────
# 콘솔 출력
# ─────────────────────────────────────────────

def print_results(cfg: dict, out: dict) -> None:
    SEP = "=" * 64
    print(SEP)
    print("  Simple Reverse Brayton Cryogenic Refrigerator Results")
    print(SEP)
    print(f"  Fluid           : {cfg['fluid']}")
    print(f"  Mass Flow Rate  : {cfg['mass_flow']:.3f} kg/s")
    print(f"  Pressure Ratio  : {out['pressure_ratio']:.4f}")
    print(f"  P_low / P_high  : {cfg['P_low']/1e3:.2f} kPa / {out['P_high']/1e3:.2f} kPa")
    print()

    # 상태점 테이블
    headers = ["State", "T [°C]", "P [kPa]", "h [kJ/kg]", "s [kJ/kgK]"]
    rows = [
        ("1 (C-in)",  out["states"][0]),
        ("2 (C-out)", out["states"][1]),
        ("2'(T-in)",  out["states"][2]),
        ("3 (T-out)", out["states"][3]),
    ]
    col_w = [10, 10, 10, 11, 11]
    fmt_h = "  " + "".join(f"{{:<{w}}}" for w in col_w)
    fmt_r = "  " + "".join(f"{{:<{w}}}" for w in col_w)

    print("  State Points:")
    print("  " + "-" * 56)
    print(fmt_h.format(*headers))
    print("  " + "-" * 56)
    for lbl, s in rows:
        print(fmt_r.format(
            lbl,
            f"{s.T_celsius():.1f}",
            f"{s.P_kPa():.2f}",
            f"{s.h_kJ():.3f}",
            f"{s.s_kJ():.4f}",
        ))
    print("  " + "-" * 56)
    print()

    # 성능 지표
    print("  Performance:")
    print(f"    Q_cold  (Refrigeration) : {out['Q_cold']/1e3:>8.3f} kW")
    print(f"    W_compressor            : {out['W_compressor']/1e3:>8.3f} kW")
    print(f"    W_turbine               : {out['W_turbine']/1e3:>8.3f} kW")
    print(f"    W_net                   : {out['W_net']/1e3:>8.3f} kW")
    print(f"    COP                     : {out['COP']:>8.4f}")
    print(f"    Energy balance error    : {out['energy_error']:.2e}")
    print(SEP)


# ─────────────────────────────────────────────
# 결과 저장
# ─────────────────────────────────────────────

def save_results(cfg: dict, out: dict) -> None:
    result_dir = out["result_dir"]
    os.makedirs(result_dir, exist_ok=True)

    # state_points.csv
    sp_path = os.path.join(result_dir, "state_points.csv")
    sp_rows = [
        ("1 (C-in)",  out["states"][0]),
        ("2 (C-out)", out["states"][1]),
        ("2'(T-in)",  out["states"][2]),
        ("3 (T-out)", out["states"][3]),
    ]
    with open(sp_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["state", "T_K", "T_degC", "P_Pa", "P_kPa", "h_J_kg", "h_kJ_kg", "s_J_kgK"])
        for lbl, s in sp_rows:
            w.writerow([
                lbl,
                f"{s.T:.4f}", f"{s.T_celsius():.4f}",
                f"{s.P:.2f}", f"{s.P_kPa():.4f}",
                f"{s.h:.4f}", f"{s.h_kJ():.4f}",
                f"{s.s:.4f}",
            ])

    # performance.csv
    perf_path = os.path.join(result_dir, "performance.csv")
    with open(perf_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["metric", "value", "unit"])
        w.writerow(["pressure_ratio",  f"{out['pressure_ratio']:.6f}", "-"])
        w.writerow(["P_low",           f"{cfg['P_low']:.2f}",          "Pa"])
        w.writerow(["P_high",          f"{out['P_high']:.2f}",         "Pa"])
        w.writerow(["Q_cold",          f"{out['Q_cold']:.4f}",         "W"])
        w.writerow(["W_compressor",    f"{out['W_compressor']:.4f}",   "W"])
        w.writerow(["W_turbine",       f"{out['W_turbine']:.4f}",      "W"])
        w.writerow(["W_net",           f"{out['W_net']:.4f}",          "W"])
        w.writerow(["COP",             f"{out['COP']:.6f}",            "-"])
        w.writerow(["energy_error",    f"{out['energy_error']:.2e}",   "-"])
        w.writerow(["mass_flow",       f"{cfg['mass_flow']:.4f}",      "kg/s"])

    print(f"\n  Results saved to: {result_dir}/")
    print(f"    {os.path.basename(sp_path)}")
    print(f"    {os.path.basename(perf_path)}")


# ─────────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────────

def main():
    args = parse_args()

    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    out = solve(cfg)
    print_results(cfg, out)
    save_results(cfg, out)


if __name__ == "__main__":
    main()
