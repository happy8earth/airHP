"""
main.py
───────
사용법:
  python main.py --config configs/simple_baseline.yaml
  python main.py --config configs/recuperated_baseline.yaml
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

_CYCLE_MENU = {
    "1": ("Simple Brayton",      "configs/simple_baseline.yaml"),
    "2": ("Recuperated Brayton", "configs/recuperated_baseline.yaml"),
}


def parse_args():
    p = argparse.ArgumentParser(description="Reverse Brayton Cryogenic Refrigerator")
    p.add_argument("--config", default=None,
                   help="YAML 설정 파일 경로 (생략 시 대화형 선택)")
    return p.parse_args()


def _select_config_interactively() -> str:
    """--config 가 생략된 경우 사이클 선택 메뉴 표시."""
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
# 콘솔 출력
# ─────────────────────────────────────────────

def print_results(cfg: dict, out: dict) -> None:
    SEP = "=" * 64
    print(SEP)
    print("  Reverse Brayton Cryogenic Refrigerator Results")
    print(SEP)
    print(f"  Cycle           : {out['cycle']}")
    print(f"  Fluid           : {cfg['fluid']}")
    print(f"  Mass Flow Rate  : {cfg['mass_flow']:.3f} kg/s")
    print(f"  Pressure Ratio  : {out['pressure_ratio']:.4f}")
    print(f"  P_low / P_high  : {cfg['P_low']/1e3:.2f} kPa / {out['P_high']/1e3:.2f} kPa")
    print()

    # 상태점 테이블 (상태 수 자동 대응)
    headers = ["State", "T [°C]", "P [kPa]", "h [kJ/kg]", "s [kJ/kgK]"]
    rows = list(zip(out["state_labels"], out["states"]))
    col_w = [12, 10, 10, 11, 11]
    fmt_h = "  " + "".join(f"{{:<{w}}}" for w in col_w)
    fmt_r = "  " + "".join(f"{{:<{w}}}" for w in col_w)

    print("  State Points:")
    print("  " + "-" * 58)
    print(fmt_h.format(*headers))
    print("  " + "-" * 58)
    for lbl, s in rows:
        print(fmt_r.format(
            lbl,
            f"{s.T_celsius():.1f}",
            f"{s.P_kPa():.2f}",
            f"{s.h_kJ():.3f}",
            f"{s.s_kJ():.4f}",
        ))
    print("  " + "-" * 58)
    print()

    # 성능 지표
    print("  Performance:")
    print(f"    Q_cold  (Refrigeration) : {out['Q_cold']/1e3:>8.3f} kW")
    print(f"    W_compressor            : {out['W_compressor']/1e3:>8.3f} kW")
    print(f"    W_turbine               : {out['W_turbine']/1e3:>8.3f} kW")
    print(f"    W_net                   : {out['W_net']/1e3:>8.3f} kW")
    if out.get("Q_recuperator", 0.0) > 0:
        print(f"    Q_recuperator           : {out['Q_recuperator']/1e3:>8.3f} kW")
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
    with open(sp_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["state", "T_K", "T_degC", "P_Pa", "P_kPa", "h_J_kg", "h_kJ_kg", "s_J_kgK"])
        for lbl, s in zip(out["state_labels"], out["states"]):
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
        w.writerow(["cycle",          out["cycle"],                        "-"])
        w.writerow(["pressure_ratio", f"{out['pressure_ratio']:.6f}",      "-"])
        w.writerow(["P_low",          f"{cfg['P_low']:.2f}",               "Pa"])
        w.writerow(["P_high",         f"{out['P_high']:.2f}",              "Pa"])
        w.writerow(["Q_cold",         f"{out['Q_cold']:.4f}",              "W"])
        w.writerow(["W_compressor",   f"{out['W_compressor']:.4f}",        "W"])
        w.writerow(["W_turbine",      f"{out['W_turbine']:.4f}",           "W"])
        w.writerow(["W_net",          f"{out['W_net']:.4f}",               "W"])
        w.writerow(["COP",            f"{out['COP']:.6f}",                 "-"])
        if out.get("Q_recuperator", 0.0) > 0:
            w.writerow(["Q_recuperator", f"{out['Q_recuperator']:.4f}",    "W"])
        w.writerow(["energy_error",   f"{out['energy_error']:.2e}",        "-"])
        w.writerow(["mass_flow",      f"{cfg['mass_flow']:.4f}",           "kg/s"])

    print(f"\n  Results saved to: {result_dir}/")
    print(f"    {os.path.basename(sp_path)}")
    print(f"    {os.path.basename(perf_path)}")


# ─────────────────────────────────────────────
# 진입점
# ─────────────────────────────────────────────

def main():
    args = parse_args()

    config_path = args.config if args.config else _select_config_interactively()

    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    out = solve(cfg)
    print_results(cfg, out)
    save_results(cfg, out)

2
if __name__ == "__main__":
    main()
