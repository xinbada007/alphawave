# Data Availability Matrix (Phase 0 Probe Result)

_Generated: 2026-05-05 23:24:54_


**Symbols probed:** HK=`00700`, CN=`600519`, US=`MSFT`


## Summary Matrix

| Status | Priority | Market | Category | Source | Rows | Detail |
|---|---|---|---|---|---|---|
| ✅ OK | MANDATORY | HK | price | `ak.stock_hk_hist (turnover/amount/amplitude)` | 80 | all required fields present: ['成交量', '成交额', '振幅', '换手率'] |
| ✅ OK | MANDATORY | CN | price | `ak.stock_zh_a_hist (turnover/amount/amplitude)` | 77 | all required fields present |
| ✅ OK | MANDATORY | HK | index | `HK Index (HSI) daily` | 8874 | via stock_hk_index_daily_em, last={'date': '2026-05-05', 'open': 25945.75, 'high |
| ✅ OK | MANDATORY | CN | index | `CN Index (CSI300) daily` | 5899 | rows=5899 |
| ✅ OK | IMPORTANT | HK | event | `HK Corporate Notice / Announcement (news_em fallback)` | 10 | via stock_news_em (Chinese news+notice stream) |
| ✅ OK | IMPORTANT | CN | event | `CN Corporate Notice / Announcement` | 9 | via stock_notice_report |
| ✅ OK | IMPORTANT | HK | flow | `Southbound Holdings (HK Connect)` | 598 | via stock_hk_ggt_components_em |
| ✅ OK | OPTIONAL | CN | flow | `CN Block Trade (大宗交易)` | 4257 | via stock_dzjy_mrtj, rows=4257 |
| ✅ OK | OPTIONAL | CN | flow | `CN Dragon-Tiger List (龙虎榜)` | 6173 | via stock_lhb_detail_em, rows=6173 |
| ✅ OK | OPTIONAL | US | price | `OpenBB equity.price.historical (US, vwap?)` | 84 | vwap present, n=84 |
| ✅ OK | OPTIONAL | US | index | `US Index (SPY) daily via OpenBB` | 84 | rows=84 |

## Blocking Assessment

✅ **All MANDATORY data sources OK or PARTIAL** — Phase 1-2 can proceed.


## Field-Level Findings

### ak.stock_hk_hist (turnover/amount/amplitude)

- **Status:** ✅ OK
- **Columns:** `日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率`
- **Rows:** 80
- **Elapsed:** 0.33s

### ak.stock_zh_a_hist (turnover/amount/amplitude)

- **Status:** ✅ OK
- **Columns:** `日期, 股票代码, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率`
- **Rows:** 77
- **Elapsed:** 0.12s

### HK Index (HSI) daily

- **Status:** ✅ OK
- **Columns:** `date, open, high, low, latest`
- **Rows:** 8874
- **Elapsed:** 3.79s

### CN Index (CSI300) daily

- **Status:** ✅ OK
- **Columns:** `date, open, high, low, close, volume`
- **Rows:** 5899
- **Elapsed:** 0.21s

### HK Corporate Notice / Announcement (news_em fallback)

- **Status:** ✅ OK
- **Columns:** `关键词, 新闻标题, 新闻内容, 发布时间, 文章来源, 新闻链接`
- **Rows:** 10
- **Elapsed:** 0.16s

### CN Corporate Notice / Announcement

- **Status:** ✅ OK
- **Columns:** `代码, 名称, 公告标题, 公告类型, 公告日期, 网址`
- **Rows:** 9
- **Elapsed:** 0.40s

### Southbound Holdings (HK Connect)

- **Status:** ✅ OK
- **Columns:** `序号, 代码, 名称, 最新价, 涨跌额, 涨跌幅, 今开, 最高, 最低, 昨收, 成交量, 成交额`
- **Rows:** 598
- **Elapsed:** 5.48s

### CN Block Trade (大宗交易)

- **Status:** ✅ OK
- **Columns:** `序号, 交易日期, 证券代码, 证券简称, 涨跌幅, 收盘价, 成交价, 折溢率, 成交笔数, 成交总量, 成交总额, 成交总额/流通市值`
- **Rows:** 4257
- **Elapsed:** 0.57s

### CN Dragon-Tiger List (龙虎榜)

- **Status:** ✅ OK
- **Columns:** `序号, 代码, 名称, 上榜日, 解读, 收盘价, 涨跌幅, 龙虎榜净买额, 龙虎榜买入额, 龙虎榜卖出额, 龙虎榜成交额, 市场总成交额, 净买额占总成交比, 成交额占总成交比, 换手率` (+6 more)
- **Rows:** 6173
- **Elapsed:** 3.25s

### OpenBB equity.price.historical (US, vwap?)

- **Status:** ✅ OK
- **Columns:** `date, open, high, low, close, volume, vwap, split_ratio, dividend`
- **Rows:** 84
- **Elapsed:** 1.38s

### US Index (SPY) daily via OpenBB

- **Status:** ✅ OK
- **Columns:** `date, open, high, low, close, volume, vwap, split_ratio, dividend`
- **Rows:** 84
- **Elapsed:** 0.53s


## Recommended Phase Routing

| Phase | Decision | Reason |
|---|---|---|
| **Phase 1** VolumeAnomalyProfiler | GO | depends on HK/CN price |
| **Phase 2** turnover/amount multidim | GO | depends on HK price w/ turnover |
| **Phase 3** Corporate Action Layer | GO (full) | event APIs |
| **Phase 4** Distribution Patterns | GO | pure math, no extra deps |
| **Phase 5** Market Relative | GO | index APIs |
| **Phase 6** Risk Scorer | GO (auto-redistribute weights for unavailable subscores) | depends on prior phases |
| **Phase 7** Flow Signals | GO (full) | southbound/block/LHB |
## VWAP 现状（Phase 0.5 集成验证补录，2026-05-05）

| 路径 | amount 列 | vwap 列 | 实际状况 | 派生策略 |
|---|---|---|---|---|
| AkShare HK | ✅ 有 | ❌ 无 | 完整 | `vwap = amount/volume`（已落地） |
| AkShare CN | ✅ 有 | ❌ 无 | 完整 | `vwap = amount/volume`（已落地） |
| OpenBB US (yfinance) | ❌ 无 | ⚠️ 有但全 None | vwap 列存在但 nullable，全为 None | 跳过派生；**Phase 4 必须用 `typical_price=(H+L+C)/3` 兜底** |

⚠️ **关键事实**：OpenBB 美股的 `vwap` 字段并非"原生有数据"，而是空列存在。
之前 README/GEMINI.md 的假设是错误的。Phase 4 distribution_patterns 必须走 typical_price fallback。
