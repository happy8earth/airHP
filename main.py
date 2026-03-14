"""
main.py
───────
사용법:
  python main.py --config configs/simple_baseline.yaml
  python main.py --config configs/recuperated_baseline.yaml
  python main.py --config configs/bypass_a_baseline.yaml
"""

import argparse
import os
import sys
import yaml
import csv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from cycle_solver import solve
from bypass_solver import solve as bypass_solve
from coupled_solver import solve as coupled_solve

_BYPASS_CYCLES = {"bypass_a_brayton"}


# ─────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────

_CYCLE_MENU = {
    "1": ("Simple Brayton",      "configs/simple_baseline.yaml"),
    "2": ("Recuperated Brayton", "configs/recuperated_baseline.yaml"),
    "3": ("Bypass-A Brayton",    "configs/bypass_a_baseline.yaml"),
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
    if "x_bypass" in out:
        x_max_str = f"  /  x_max = {out['x_max']*100:.1f}%" if "x_max" in out else ""
        print(f"  Bypass Fraction : {out['x_bypass']:.4f}  (x = {out['x_bypass']*100:.2f}%{x_max_str})")
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
    print(f"    W_expander               : {out['W_expander']/1e3:>8.3f} kW")
    print(f"    W_net                   : {out['W_net']/1e3:>8.3f} kW")
    if "Q_recuperator" in out:
        # Sign convention: Q_recuperator = -RecupHot.Q_dot
        #   RecupHot.Q_dot < 0 -> Q_recuperator > 0 (normal)
        #   RecupHot.Q_dot > 0 -> Q_recuperator < 0 (reversed)
        print(f"    Q_recuperator : {out['Q_recuperator']/1e3:>8.3f} kW")
    print(f"    COP                     : {out['COP']:>8.4f}")
    if "T_sec_out" in out and out["T_sec_out"] is not None:
        if "T_sec_out_target" in out:
            print(f"    T_sec_out (IM-7 out)    : {out['T_sec_out'] - 273.15:>7.2f} °C"
                  f"  (target: {out['T_sec_out_target'] - 273.15:.2f} °C)")
        else:
            print(f"    T_sec_out (IM-7 out)    : {out['T_sec_out'] - 273.15:>7.2f} °C")
    if "y_sec" in out:
        print(f"    y_sec (IM-7 bypass)     : {out['y_sec']:.4f}")
        print(f"    T_load_sec_in           : {out['T_load_sec_in'] - 273.15:>7.2f} °C")
        print(f"    T_load_sec_out          : {out['T_load_sec_out'] - 273.15:>7.2f} °C")
        print(f"    Q_heater                : {out['Q_heater']/1e3:>8.3f} kW"
              f"  (Q_cold - Q_heater = {(out['Q_cold']-out['Q_heater'])/1e3:+.3f} kW)")
    print(f"    Energy balance error    : {out['energy_error']:.2e}")

    # HX 상세 (UA·LMTD 파라미터)
    hx_results = [r for r in out["results"] if r.extra.get("UA") is not None]
    if hx_results:
        print()
        print("  Heat Exchangers (UA·LMTD):")
        hdr = f"    {'Component':<16} {'UA [W/K]':>10} {'LMTD [K]':>10} {'Q [kW]':>8}"
        eps_col = any(r.extra.get("epsilon") is not None for r in hx_results)
        if eps_col:
            hdr += f"  {'ε [-]':>6}"
        print(hdr)
        print("  " + "-" * (50 + (9 if eps_col else 0)))
        for r in hx_results:
            q_kw = r.Q_dot / 1e3 if "Q_signed" in r.extra else abs(r.Q_dot) / 1e3
            line = (f"    {r.label:<16} {r.extra['UA']:>10.1f} "
                    f"{r.extra['LMTD']:>10.2f} {q_kw:>8.3f}")
            if eps_col and r.extra.get("epsilon") is not None:
                line += f"  {r.extra['epsilon']:>6.4f}"
            print(line)
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

        sec = out.get("sec_temps", {})
        load_info = sec.get("load", {})
        ac_info   = sec.get("ac",   {})

        # 2차측 조회: state 인덱스 → (레이블, T_K)
        # counter-flow: 2차측 입구는 공기 출구 끝, 2차측 출구는 공기 입구 끝
        load_by_idx = {}
        if load_info:
            load_by_idx[load_info["air_in_idx"]]  = ("load_sec_out", load_info["T_sec_out"])
            load_by_idx[load_info["air_out_idx"]] = ("load_sec_in",  load_info["T_sec_in"])
        ac_by_idx = {}
        if ac_info:
            ac_by_idx[ac_info["air_in_idx"]]  = ("ac_sec_out", ac_info["T_sec_out"])
            ac_by_idx[ac_info["air_out_idx"]] = ("ac_sec_in",  ac_info["T_sec_in"])

        w.writerow(["state", "T_K", "T_degC", "P_Pa", "P_kPa", "h_J_kg", "h_kJ_kg", "s_J_kgK",
                    "load_sec", "load_T_K", "load_T_degC",
                    "ac_sec",   "ac_T_K",   "ac_T_degC"])
        for i, (lbl, s) in enumerate(zip(out["state_labels"], out["states"])):
            load_lbl, load_T = load_by_idx.get(i, ("", None))
            ac_lbl,   ac_T   = ac_by_idx.get(i,   ("", None))
            w.writerow([
                lbl,
                f"{s.T:.4f}", f"{s.T_celsius():.4f}",
                f"{s.P:.2f}", f"{s.P_kPa():.4f}",
                f"{s.h:.4f}", f"{s.h_kJ():.4f}",
                f"{s.s:.4f}",
                load_lbl,
                f"{load_T:.4f}"       if load_T is not None else "",
                f"{load_T-273.15:.4f}" if load_T is not None else "",
                ac_lbl,
                f"{ac_T:.4f}"         if ac_T is not None else "",
                f"{ac_T-273.15:.4f}"  if ac_T is not None else "",
            ])

    # performance.csv
    perf_path = os.path.join(result_dir, "performance.csv")
    with open(perf_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        # hx_load effectiveness (epsilon)
        hx_load_eps = None
        for r in out.get("results", []):
            if r.label == "LoadHX" and r.extra.get("epsilon") is not None:
                hx_load_eps = r.extra["epsilon"]
                break

        w.writerow(["metric", "value", "unit"])
        w.writerow(["cycle",          out["cycle"],                        "-"])
        w.writerow(["pressure_ratio", f"{out['pressure_ratio']:.6f}",      "-"])
        w.writerow(["P_low",          f"{cfg['P_low']:.2f}",               "Pa"])
        w.writerow(["P_high",         f"{out['P_high']:.2f}",              "Pa"])
        if "x_bypass" in out:
            w.writerow(["x_bypass",   f"{out['x_bypass']:.6f}",           "-"])
        w.writerow(["Q_cold",         f"{out['Q_cold']:.4f}",              "W"])
        if hx_load_eps is not None:
            w.writerow(["hx_load_effectiveness", f"{hx_load_eps:.6f}",     "-"])
        if out.get("Q_aftercooler", 0.0) > 0:
            w.writerow(["Q_aftercooler", f"{out['Q_aftercooler']:.4f}",   "W"])
        w.writerow(["W_compressor",   f"{out['W_compressor']:.4f}",        "W"])
        w.writerow(["W_expander",      f"{out['W_expander']:.4f}",          "W"])
        w.writerow(["W_net",          f"{out['W_net']:.4f}",               "W"])
        w.writerow(["COP",            f"{out['COP']:.6f}",                 "-"])
        w.writerow(["Q_recuperator", f"{out.get('Q_recuperator', 0.0):.4f}", "W"])
        _load_sec = out.get("sec_temps", {}).get("load", {})
        if _load_sec:
            w.writerow(["T_load_sec_out", f"{_load_sec['T_sec_out']-273.15:.4f}", "degC"])
            w.writerow(["T_load_sec_in",  f"{_load_sec['T_sec_in'] -273.15:.4f}", "degC"])
        w.writerow(["energy_error",   f"{out['energy_error']:.2e}",        "-"])
        w.writerow(["mass_flow",      f"{cfg['mass_flow']:.4f}",           "kg/s"])
        # ── Load측 2차 회로 (IM-7) ──────────────────────────────────────
        # coupled_solver: 필드가 out에 직접 포함
        if "y_sec" in out:
            w.writerow(["y_sec",           f"{out['y_sec']:.6f}",                          "-"])
            w.writerow(["mdot_load_sec",   f"{out['mdot_load_sec']:.6f}",                  "kg/s"])
            w.writerow(["T_chuck_sec_in",  f"{out['T_chuck_sec_in']  - 273.15:.4f}",       "degC"])
            w.writerow(["T_chuck_sec_out", f"{out['T_chuck_sec_out'] - 273.15:.4f}",       "degC"])
            w.writerow(["T_load_sec_in",   f"{out['T_load_sec_in']   - 273.15:.4f}",       "degC"])
            w.writerow(["T_load_sec_out",  f"{out['T_load_sec_out']  - 273.15:.4f}",       "degC"])
            w.writerow(["Q_chuck",         f"{out['Q_chuck']:.2f}",                        "W"])
            w.writerow(["Q_heater",        f"{out['Q_heater']:.2f}",                       "W"])

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

    if cfg.get("cycle") in _BYPASS_CYCLES:
        if "load_side" in cfg:
            out = coupled_solve(cfg)
        else:
            out = bypass_solve(cfg)
    else:
        out = solve(cfg)

    print_results(cfg, out)
    save_results(cfg, out)


if __name__ == "__main__":
    main()
