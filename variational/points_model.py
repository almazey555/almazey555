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
# Referral bonus (+1 pt per 10 pts earned by referrals) and campaigns (On-Chain
# Trader Rewards, cap 150k) sit on top of the nominal 3M + 150k/week. Calibrated to
# ~9.55M total for a program ending with the Oct 2 drop (end of Q3, 42 weeks).
POINTS_MULT = 9.55e6 / (RETRO_POINTS + 42 * WEEKLY_POINTS)

# Day-1 FDV scenarios (USD) and subjective probabilities
SCENARIOS = [
    ("Bear",         600e6, 0.15),   # edgeX/GRVT-like FDV/OI ~0.4-1x
    ("Conservative", 1_000e6, 0.25),
    ("Base",       1_500e6, 0.30),   # ~Polymarket median, ~1.7x OI
    ("Bull",       2_800e6, 0.22),   # ~3-4x OI (Aster-like)
    ("Euphoria",   5_000e6, 0.08),   # ~6x OI (Lighter-like)
]

# DefiLlama perp snapshot 2026-09-24: (OI, 30d volume, current FDV)
VARIATIONAL_OI = 878.25e6
VARIATIONAL_VOL_7D = 18.168e9
VARIATIONAL_VOL_30D = 48.157e9
COMPS = [
    ("Hyperliquid", 9.06e9,   219.983e9, 89e9),
    ("Aster",       1.411e9,  69.11e9,   5.6e9),
    ("Lighter",     835.86e6, 54.476e9,  5.16e9),
    ("edgeX",       618.36e6, 40.764e9,  0.61e9),
    ("Grvt",        471.1e6,  14.642e9,  0.19e9),
]

# TGE timing scenarios: last weekly drop before TGE
TGE_DATES = [
    ("Late Oct 2026",  date(2026, 10, 30), 0.05),
    ("Mid Nov 2026",   date(2026, 11, 13), 0.15),
    ("Mid Dec 2026",   date(2026, 12, 18), 0.35),  # ~1y after points launch (Dec 17, 2025)
    ("Late Dec 2026",  date(2026, 12, 25), 0.25),  # Lighter-style (LIT TGE Dec 30, 2025)
    ("Slip: Feb 2027", date(2027, 2, 26),  0.20),
]


def weeks_through(d: date) -> int:
    """Number of weekly drops made on or before date d."""
    if d < FIRST_WEEKLY:
        return 0
    return (d - FIRST_WEEKLY).days // 7 + 1


def total_points(last_drop: date) -> float:
    return (RETRO_POINTS + weeks_through(last_drop) * WEEKLY_POINTS) * POINTS_MULT


def value_per_point(fdv: float, points: float) -> float:
    return fdv * AIRDROP_SHARE / points


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--my-points", type=float, default=None)
    ap.add_argument("--my-cost", type=float, default=None,
                    help="total farming cost so far in USD (spread + funding + net PnL loss - refunds)")
    ap.add_argument("--otc-price", type=float, default=None,
                    help="OTC/pre-market price per point (Whales-style: seller posts 100%% collateral)")
    args = ap.parse_args()

    today = date(2026, 9, 24)
    now_pts = total_points(today)
    print(f"Weekly drops so far (as of {today}): {weeks_through(today)}")
    print(f"Points issued so far (incl. referral/campaign x{POINTS_MULT:.3f}): {now_pts/1e6:.2f}M")
    print(f"End of Q3 (Oct 2 drop): {total_points(date(2026, 10, 2))/1e6:.2f}M;"
          f" effective weekly emission ~{WEEKLY_POINTS * POINTS_MULT/1e3:.0f}k\n")

    print("TGE timing -> total points at TGE")
    exp_pts = 0.0
    for name, d, p in TGE_DATES:
        tp = total_points(d)
        exp_pts += p * tp
        dil = now_pts / tp
        print(f"  {name:16s} last drop {d}  weeks={weeks_through(d):3d}  total={tp/1e6:6.2f}M"
              f"  (holder who stops now keeps {dil:5.1%} of current share)  p={p:.0%}")
    print(f"  Probability-weighted total points: {exp_pts/1e6:.2f}M\n")

    eoq3 = total_points(date(2026, 10, 2))
    print("Announcement effect vs pre-announcement expectation (TGE right after Q3):")
    for exp_share in (0.20, 0.25):
        for name, d, _ in TGE_DATES:
            ratio = (AIRDROP_SHARE / total_points(d)) / (exp_share / eoq3)
            print(f"  expected {exp_share:.0%} airdrop, TGE {name:15s}: value/pt x{ratio:.2f}")
    print()

    pts_grid = [10.0e6, 10.5e6, 11.0e6, 11.5e6, 12.0e6, 13.0e6]
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

    print("Comparables: FDV/OI and FDV/30d volume -> implied Variational FDV")
    geo_oi, geo_vol, n = 1.0, 1.0, 0
    for name, oi, vol, fdv in COMPS:
        m_oi, m_vol = fdv / oi, fdv / vol
        print(f"  {name:12s} FDV ${fdv/1e9:5.2f}B  FDV/OI {m_oi:5.2f}x -> ${m_oi*VARIATIONAL_OI/1e9:5.2f}B"
              f"   FDV/vol30d {m_vol:.3f} -> ${m_vol*VARIATIONAL_VOL_30D/1e9:5.2f}B")
        if name != "Hyperliquid":
            geo_oi *= m_oi
            geo_vol *= m_vol
            n += 1
    geo_oi, geo_vol = geo_oi ** (1 / n), geo_vol ** (1 / n)
    print(f"  Geometric mean ex-HL: FDV/OI {geo_oi:.2f}x -> ${geo_oi*VARIATIONAL_OI/1e9:.2f}B;"
          f" FDV/vol {geo_vol:.3f} -> ${geo_vol*VARIATIONAL_VOL_30D/1e9:.2f}B")
    print(f"  Variational vol30d/OI = {VARIATIONAL_VOL_30D/VARIATIONAL_OI:.0f}x"
          f" (Hyperliquid {COMPS[0][2]/COMPS[0][1]:.0f}x)\n")

    # Rough farming-cost estimate if points were purely volume-proportional.
    # Effective spread paid per $ of volume: ~1.2-1.6 bps from spring gross-spread
    # revenue vs volume; up to ~3 bps if quoted 4-6 bps spread is paid half per side.
    print("Farming cost if points ~ volume (spread only, no PnL/funding/refunds)")
    for label, weekly_vol in (("last 7d", VARIATIONAL_VOL_7D), ("30d avg", VARIATIONAL_VOL_30D / 30 * 7)):
        vol_per_point = weekly_vol / WEEKLY_POINTS
        costs = "  ".join(f"{bps} bps ~${vol_per_point * bps / 1e4:5.1f}" for bps in (1.2, 1.6, 3.0))
        print(f"  {label}: ~${vol_per_point/1e3:.0f}k volume/pt;  {costs}")
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
        print()

    if args.otc_price:
        otc_report(args.otc_price, base_pts, args.my_points)


def otc_report(price: float, pts: float, my_points: float | None) -> None:
    """Sell-now-on-OTC vs hold, Whales Market style settlement.

    Seller locks collateral = price. After TGE the seller either delivers tokens
    (gets price + collateral back) or defaults (loses collateral, keeps tokens).
    So seller ends with max(price, V - price) per point, buyer with min(V, 2*price) - price.
    """
    implied = price * pts / AIRDROP_SHARE
    print(f"OTC ${price:.2f}/pt -> implied day-1 FDV ${implied/1e9:.2f}B at {pts/1e6:.2f}M points"
          f"  (FDV/OI {implied/VARIATIONAL_OI:.2f}x)")
    print(f"  Selling = betting value < ${price:.0f}/pt: gain (price - V), capped at +/-${price:.0f}")
    ev_hold = ev_sell = 0.0
    for name, fdv, p in SCENARIOS:
        v = value_per_point(fdv, pts)
        sell = max(price, v - price)
        action = "deliver" if v <= 2 * price else "default"
        ev_hold += p * v
        ev_sell += p * sell
        print(f"  {name:13s} V=${v:6.1f}  hold ${v:6.1f}  sell ${sell:6.1f} ({action})  diff {sell - v:+6.1f}")
    print(f"  EV hold ${ev_hold:.1f}/pt, EV sell ${ev_sell:.1f}/pt -> selling costs ${ev_hold - ev_sell:.1f}/pt")
    # buyer break-even price under the scenario distribution: E[min(V, 2P)] = P
    lo, hi = 0.0, 500.0
    for _ in range(60):
        mid = (lo + hi) / 2
        payoff = sum(p * min(value_per_point(f, pts), 2 * mid) for _, f, p in SCENARIOS)
        lo, hi = (mid, hi) if payoff > mid else (lo, mid)
    print(f"  Fair OTC price under these scenarios (buyer break-even): ~${lo:.0f}/pt")
    if my_points:
        print(f"  For {my_points:,.0f} pts: collateral ${price * my_points:,.0f};"
              f" expected cost of selling all ${(ev_hold - ev_sell) * my_points:,.0f}")


if __name__ == "__main__":
    main()
