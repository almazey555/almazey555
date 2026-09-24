"""Variational ($VAR) point value model.

Usage:
    python3 points_model.py                       # print all tables
    python3 points_model.py --my-points 1200 --my-cost 9000

All inputs are assumptions from public sources as of 2026-09-24; edit the
constants below as new data comes in (TGE date, Polymarket ladder, etc.).
"""
import argparse
from datetime import date, timedelta

AIRDROP_SHARE = 0.32          # Genesis Distribution, 100% unlocked at TGE
RETRO_POINTS = 3_000_000      # retro drop at program launch (Dec 17, 2025)
WEEKLY_POINTS = 150_000       # weekly drop, every Friday 00:00 UTC
FIRST_WEEKLY = date(2025, 12, 19)  # week 1 distribution (week 6 = Jan 23, 2026)
EXTRA_POINTS = 150_000        # On-Chain Trader Rewards campaign cap (since Aug 12, 2026);
                              # referral bonus may add more on top - unknown

# Day-1 FDV scenarios (USD) and subjective probabilities
SCENARIOS = [
    ("Bear",        500e6, 0.20),
    ("Conservative", 800e6, 0.25),
    ("Base",       1_300e6, 0.30),
    ("Bull",       2_200e6, 0.18),
    ("Euphoria",   4_000e6, 0.07),
]

# TGE timing scenarios: last weekly drop before TGE
TGE_DATES = [
    ("Late Oct 2026",  date(2026, 10, 30), 0.15),
    ("Mid Nov 2026",   date(2026, 11, 13), 0.20),
    ("Early Dec 2026", date(2026, 12, 4),  0.30),
    ("Late Dec 2026",  date(2026, 12, 25), 0.15),
    ("Slip: Feb 2027", date(2027, 2, 26),  0.20),
]


def weeks_through(d: date) -> int:
    """Number of weekly drops made on or before date d."""
    if d < FIRST_WEEKLY:
        return 0
    return (d - FIRST_WEEKLY).days // 7 + 1


def total_points(last_drop: date, extras: float = EXTRA_POINTS) -> float:
    return RETRO_POINTS + weeks_through(last_drop) * WEEKLY_POINTS + extras


def value_per_point(fdv: float, points: float) -> float:
    return fdv * AIRDROP_SHARE / points


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--my-points", type=float, default=None)
    ap.add_argument("--my-cost", type=float, default=None,
                    help="total farming cost so far in USD (spread + funding + net PnL loss - refunds)")
    args = ap.parse_args()

    today = date(2026, 9, 24)
    now_pts = total_points(today, extras=0)
    print(f"Weekly drops so far (as of {today}): {weeks_through(today)}")
    print(f"Points issued so far (retro + weekly, no extras): {now_pts/1e6:.2f}M")
    print(f"After Fri Sep 25 drop: {total_points(date(2026, 9, 25), 0)/1e6:.2f}M\n")

    print("TGE timing -> total points at TGE (incl. ~150k campaign extras)")
    exp_pts = 0.0
    for name, d, p in TGE_DATES:
        tp = total_points(d)
        exp_pts += p * tp
        dil = now_pts / tp
        print(f"  {name:16s} last drop {d}  weeks={weeks_through(d):3d}  total={tp/1e6:6.2f}M"
              f"  (holder who stops now keeps {dil:5.1%} of current share)  p={p:.0%}")
    print(f"  Probability-weighted total points: {exp_pts/1e6:.2f}M\n")

    pts_grid = [9.5e6, 10.0e6, 10.5e6, 11.0e6, 11.5e6, 12.5e6]
    print("USD per point  (rows: day-1 FDV, cols: total points at TGE)")
    print("  FDV      " + "".join(f"{p/1e6:>8.1f}M" for p in pts_grid))
    for fdv in [300e6, 500e6, 800e6, 1_000e6, 1_300e6, 1_500e6, 2_000e6, 3_000e6, 5_000e6]:
        row = "".join(f"{value_per_point(fdv, p):>9.1f}" for p in pts_grid)
        print(f"  ${fdv/1e9:>4.1f}B  {row}")
    print()

    base_pts = exp_pts
    ev = 0.0
    print(f"Scenarios at {base_pts/1e6:.2f}M points:")
    for name, fdv, p in SCENARIOS:
        v = value_per_point(fdv, base_pts)
        ev += p * v
        print(f"  {name:13s} FDV ${fdv/1e9:4.2f}B  -> ${v:6.1f}/pt   p={p:.0%}")
    ev_fdv = sum(f * p for _, f, p in SCENARIOS)
    print(f"  Probability-weighted FDV: ${ev_fdv/1e9:.2f}B  ->  EV ${ev:.1f}/pt")
    # median scenario by cumulative probability
    cum = 0.0
    for name, fdv, p in SCENARIOS:
        cum += p
        if cum >= 0.5:
            print(f"  Median scenario: {name} (${value_per_point(fdv, base_pts):.1f}/pt)\n")
            break

    # Rough farming-cost estimate if points were purely volume-proportional
    # 30d volume snapshots in sources range $16-48B; 2026 average ~$28B ($240B Jan 1-Sep 18).
    # Effective spread paid per $ of volume: ~1.5-3 bps (4-6 bps quoted spread, half per side).
    for vol_30d in (20e9, 28e9, 48e9):
        weekly_vol = vol_30d / 30 * 7
        vol_per_point = weekly_vol / WEEKLY_POINTS
        for bps in (1.5, 3.0):
            cost = vol_per_point * bps / 1e4
            print(f"  30d vol ${vol_30d/1e9:.0f}B -> ~${vol_per_point/1e3:.0f}k volume/pt;"
                  f" at {bps} bps effective spread ~${cost:.1f}/pt")
    print()

    if args.my_points:
        print(f"Your points: {args.my_points:,.0f}")
        for name, fdv, p in SCENARIOS:
            v = value_per_point(fdv, base_pts) * args.my_points
            print(f"  {name:13s} ${v:,.0f}")
        print(f"  EV            ${ev * args.my_points:,.0f}")
        if args.my_cost:
            cpp = args.my_cost / args.my_points
            be_fdv = cpp * base_pts / AIRDROP_SHARE
            print(f"  Your cost/pt ${cpp:.2f} -> break-even day-1 FDV ${be_fdv/1e9:.2f}B")


if __name__ == "__main__":
    main()
