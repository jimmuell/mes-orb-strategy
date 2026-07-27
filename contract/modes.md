# WIT mode vocabulary — v1

> The enumerated, versioned mode tokens the v1 engine supports (WIT-03 §3.4/§3.5). The template→config mapper reads each config-relevant field's `mode` + `params` (the machine param channel added in WIT-P3c-1) — **never the `value` prose**. A field whose `mode` is not in the v1 vocabulary for its dimension → **`UNSUPPORTED_CONSTRUCT`** (fail fast; see bottom). Each unknown token is a one-line engine backlog item.
>
> Ownership: `contract/` holds the machine copies (this file + the wire JSON Schemas); `docs/wit/WIT-03-api-contract.md` holds the prose contract; `docs/wit/WIT-02-strategy-template-schema.md` owns the template semantics. Contract changes are PR'd against `contract/` + WIT-03 and lead-engineer approved (WIT-03 §7).

## Class A — StrategyConfig dimensions (backtest)

| Dimension | Field | v1 mode tokens | `params` | Runner realization |
|---|---|---|---|---|
| `bias` | D1 | `vp_value_area_break` · `orb_break`† · `none`† | — | `build_signals_for_day` direction: close body through VAH→long / VAL→short (`vp_orb_runner.py`) |
| `setup` | D2 | `volume_profile_range` · `opening_range`† | `{range_start, range_end, value_area_pct, granularity}` | `build_volume_profile` over the window (`vp_orb_runner.py:98,103`) |
| `entry.trigger` | D3 | `bar_close_beyond_level` · `bar_body_beyond_level` | `{level}` | `_qualifies(row, dir, level, mode)` → `entry_mode` (`:135,138`) |
| `entry.level` | D3/D1 | `va_high_low` · `orb_high_low`† | — | VAH/VAL from the profile |
| `order` | D4 | `market_on_close` · `market_next_open`† | — | `process_orders_on_close=True` (`:263`) |
| `sizing` | E1 | `fixed_contracts` | `{value}` | `qty_type="fixed"`, `qty_value` (`:260`) |
| `stop` | F1 | `level_offset` · `structure`† | `{ref: poc\|va\|orb, ticks}` | `sl_price = ref ∓ ticks·tick_size` (`:146`) |
| `target` | F2 | `r_multiple` · `level`† · `none`† | `{value}` | `tp_price = entry ± value·R` (`:150,154`) |
| `time_exit` | F4 | `force_flat` · `fixed_time`† · `none`† | — | `_resolve_exit` last-RTH-bar flatten (`:195`+) |
| `same_bar` | F5 | `stop_first` · `target_first` | — | `_resolve_exit` tie-break (`:195`) |
| `session` | C1 | `rth_window` | `{entry_start, entry_last_bar, tz}` | entry-window gate (`:128`). **tz MUST be `America/New_York`** (ET wall-clock, matching the engine); any other tz → `UNSUPPORTED_CONSTRUCT` (never a silent tz conversion). |
| `filters` | C2/C3 | `none` (v1) · regime/calendar† | — | — |
| `instrument` | B1 | `futures_proxy` · `direct` | `{symbol, tick_size, tick_value, proxy_for}` | economics ($5/pt MES); `proxy_for` disclosed in the report |
| `costs` | H1/H2 | — | `{commission_per_side}` / `{slippage_ticks}` | `BacktestConfig` (`:258,259`) |
| `data.window` | J1 | — | `{window:{start,end}}` | `load_5min(start,end)` (`:222,262`) — the authoritative run window |

## Class B — EventStudyConfig dimensions (event study)

| Dimension | Field | v1 mode tokens | `params` | Runner realization |
|---|---|---|---|---|
| `event` | J1/I1 | `body_vs_trailing_median` | `{k, n_baseline}` | `event_mask` (`event_study.py:206,207`). **Note: v1 is body-vs-median, NOT `k*ATR`.** |
| `path_bucket` | J1/I1/J2 | `path_threshold` · `path_percentile` | `{spike_eff, spike_giveback_cap, pullback_p, bucket_mode}` | `bucket_series` (`:214,231`) |
| `regime` | J1 (C2 concept) | `kaufman_er_trailing_median` · `kaufman_er_insample_median` · `kaufman_er_fixed` · `adx_threshold` · `none`† | `{regime_er_m, regime_trailing_window, regime_fixed_er, regime_adx_len, regime_adx_thresh}` | `regime_series` (`:180–196`) |
| `outcomes` | J1 | — | `{horizons:[1,3,5,10], measures:[fwd_return,giveback,p_against]}` | `_add_forward_outcomes` |
| `timeframe` | B2/J1 | `5min` · `15min` | — | `build_candles` |
| `data.window` | J1 | — | `{window:{start,end}}` | `load_1min_rth(start,end)` |

`†` = declared for the vocabulary but **not engine-supported in v1** — a template requesting it fails fast with `UNSUPPORTED_CONSTRUCT` and the token enters the engine backlog (one construct at a time). The vocabulary must never over-promise: P3e's extraction prompt is generated from this file.

## UNSUPPORTED_CONSTRUCT

When a field's `mode` is absent from the v1 vocabulary for its dimension (or is a `†` declared-but-not-engine-supported token), the mapper **fails fast** and returns (WIT-03 §3.7):

```json
{"error": {"code": "UNSUPPORTED_CONSTRUCT",
           "message": "<dimension> mode '<token>' not supported in engine v1",
           "detail": {"field": "<id>", "mode": "<token>"}}}
```

Rules:
- **Never a silent skip or a guessed substitute.** A construct we can't run is a user-visible product state ("our lab doesn't support this strategy feature yet"), not a failure to hide.
- The `session.tz`-non-ET case and the baked-constant mismatches (order ≠ `market_on_close`, sizing ≠ `fixed_contracts`/1, bias ≠ `vp_value_area_break`, time_exit ≠ `force_flat`) are `UNSUPPORTED_CONSTRUCT` in v1 (the runner hardcodes these).
- Every distinct unsupported token is a one-line engine backlog entry, added one construct at a time (WIT-03 §3.4).
