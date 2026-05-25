//+------------------------------------------------------------------+
//|  OrderBlockEA.mq5  —  Order Block Strategy                      |
//|  M3 OB detection + M1 BB / EMA200 limit entry                   |
//+------------------------------------------------------------------+
#property copyright "Order Block EA"
#property version   "1.00"

#include <Trade\Trade.mqh>

// ── Strategy ──────────────────────────────────────────────────────
input group "Order Block Detection (M3)"
input double DojiBodyPct      = 0.20;   // Max body/range ratio for doji candle
input double MinImpulseBody   = 0.70;   // Min body/range ratio for impulse candle
input double MinImpulsePct    = 0.0003; // Min impulse body as fraction of price
input double MinOBSizePct     = 0.0001; // Min OB zone size as fraction of price
input int    OBExpiryBars     = 30;     // M1 bars before OB is invalidated (no touch)

input group "Entry Confirmation (M1)"
input int    EmaPeriod        = 200;
input int    BbPeriod         = 20;
input double BbStdDev         = 2.0;
input double BbTouchTol       = 0.005; // tolerance fraction for BB touching OB zone

input group "Risk & Targets"
input double RiskPercent      = 1.0;   // % risk per trade leg
input double TP1_RR           = 1.0;   // TP1 reward:risk
input double TP2_RR           = 2.0;   // TP2 reward:risk (uses ATR trailing)
input double AtrPeriod        = 14;    // ATR period for trailing stop
input double AtrMultiplier    = 1.5;   // ATR multiplier for trailing distance
input double SLBufferPct      = 0.50;  // SL buffer as fraction of OB size

input group "Protection"
input double MaxDailyDrawdown = 3.0;   // Max daily DD % before halting
input int    MaxActiveOrders  = 5;

input group "Session Filter"
input bool   UseSessionFilter = true;
input int    SessionStartUTC  = 7;
input int    SessionEndUTC    = 21;

input group "Weekend Filter"
input bool   UseWeekendFilter = true;
input int    FridayCloseHour  = 21;

input group "News Filter"
input bool   UseNewsFilter    = false;
input int    NewsMinsBefore   = 30;
input int    NewsMinsAfter    = 30;

input group "General"
input long   MagicNumber      = 20260101;
input bool   ShowPanel        = true;

// ──────────────────────────────────────────────────────────────────
CTrade Trade;

int    EmaHandleM1    = INVALID_HANDLE;
int    EmaHandleM3    = INVALID_HANDLE;
int    BbHandleM1     = INVALID_HANDLE;
int    AtrHandleM1    = INVALID_HANDLE;

struct OBZone {
    datetime time;
    int      direction;  // 1=bullish  -1=bearish
    double   ob_high;
    double   ob_low;
    double   sl_ref;
    bool     active;
    bool     triggered;
};

OBZone  OBZones[];
int     OBCount = 0;

datetime LastM3Bar  = 0;
datetime LastDayDD  = 0;
double   DayStartBalance = 0;

// ──────────────────────────────────────────────────────────────────
int OnInit()
{
    EmaHandleM1 = iMA(_Symbol, PERIOD_M1, EmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
    EmaHandleM3 = iMA(_Symbol, PERIOD_M3, EmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
    BbHandleM1  = iBands(_Symbol, PERIOD_M1, BbPeriod, 0, BbStdDev, PRICE_CLOSE);
    AtrHandleM1 = iATR(_Symbol, PERIOD_M1, (int)AtrPeriod);

    if(EmaHandleM1 == INVALID_HANDLE || EmaHandleM3 == INVALID_HANDLE ||
       BbHandleM1 == INVALID_HANDLE || AtrHandleM1 == INVALID_HANDLE)
    {
        Alert("OrderBlockEA: indicator handle creation failed");
        return INIT_FAILED;
    }

    ArrayResize(OBZones, 200);
    Trade.SetExpertMagicNumber(MagicNumber);
    Trade.SetDeviationInPoints(10);

    DayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
    LastDayDD = iTime(_Symbol, PERIOD_D1, 0);

    return INIT_SUCCEEDED;
}

void OnDeinit(int reason)
{
    if(EmaHandleM1 != INVALID_HANDLE) IndicatorRelease(EmaHandleM1);
    if(EmaHandleM3 != INVALID_HANDLE) IndicatorRelease(EmaHandleM3);
    if(BbHandleM1  != INVALID_HANDLE) IndicatorRelease(BbHandleM1);
    if(AtrHandleM1 != INVALID_HANDLE) IndicatorRelease(AtrHandleM1);
    if(ShowPanel) DeletePanel();
}

void OnTick()
{
    ResetDailyDD();
    if(DailyDDBreached()) return;
    if(IsWeekend())       return;
    if(!IsSession())      return;

    ManageTrailingStop();
    ScanM3ForOBs();
    CheckOBEntry();

    if(ShowPanel) DrawPanel();
}

// ──────────────────────────────────────────────────────────────────
// Daily drawdown guard
// ──────────────────────────────────────────────────────────────────
void ResetDailyDD()
{
    datetime dayOpen = iTime(_Symbol, PERIOD_D1, 0);
    if(dayOpen != LastDayDD) {
        DayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
        LastDayDD = dayOpen;
    }
}

bool DailyDDBreached()
{
    double bal = AccountInfoDouble(ACCOUNT_BALANCE);
    double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
    double dd  = (DayStartBalance - MathMin(bal, eq)) / DayStartBalance * 100.0;
    return dd >= MaxDailyDrawdown;
}

// ──────────────────────────────────────────────────────────────────
// M3 OB detection — runs once per new M3 bar
// ──────────────────────────────────────────────────────────────────
void ScanM3ForOBs()
{
    datetime barTime = iTime(_Symbol, PERIOD_M3, 1);
    if(barTime == LastM3Bar) return;
    LastM3Bar = barTime;

    // need at least 3 closed M3 bars: [2]=prev  [1]=doji  [0 but use 1-based: 2]=impulse
    // index 0 = current forming bar, so closed bars start at 1
    // We need:  bar[3]=prev, bar[2]=doji, bar[1]=impulse (all closed)
    double ema3[];
    ArraySetAsSeries(ema3, true);
    if(CopyBuffer(EmaHandleM3, 0, 0, 5, ema3) < 5) return;

    for(int i = 3; i >= 1; i--) {
        // doji = bar[i+1], impulse = bar[i], prev = bar[i+2]
        int doji_i    = i + 1;
        int impulse_i = i;
        int prev_i    = i + 2;

        if(prev_i > 10) continue;  // safety

        double d_o  = iOpen (_Symbol, PERIOD_M3, doji_i);
        double d_c  = iClose(_Symbol, PERIOD_M3, doji_i);
        double d_h  = iHigh (_Symbol, PERIOD_M3, doji_i);
        double d_l  = iLow  (_Symbol, PERIOD_M3, doji_i);
        double d_r  = d_h - d_l;
        if(d_r == 0) continue;
        if(MathAbs(d_c - d_o) / d_r > DojiBodyPct) continue;

        double n_o  = iOpen (_Symbol, PERIOD_M3, impulse_i);
        double n_c  = iClose(_Symbol, PERIOD_M3, impulse_i);
        double n_h  = iHigh (_Symbol, PERIOD_M3, impulse_i);
        double n_l  = iLow  (_Symbol, PERIOD_M3, impulse_i);
        double n_r  = n_h - n_l;
        double n_b  = MathAbs(n_c - n_o);
        if(n_r == 0) continue;
        if(n_b / n_r < MinImpulseBody) continue;
        if(n_b < n_c * MinImpulsePct)  continue;

        int direction = (n_c < n_o) ? -1 : 1;

        double ema_val = ema3[doji_i];
        if(ema_val == 0) continue;
        if(direction == -1 && d_c < ema_val) continue;  // bearish OB must be above EMA
        if(direction ==  1 && d_c > ema_val) continue;  // bullish OB must be below EMA

        // imbalance: impulse must break through prev bar
        double p_h = iHigh(_Symbol, PERIOD_M3, prev_i);
        double p_l = iLow (_Symbol, PERIOD_M3, prev_i);
        if(direction == -1 && n_c >= p_l) continue;
        if(direction ==  1 && n_c <= p_h) continue;

        double ob_high = MathMax(d_o, d_c);
        double ob_low  = MathMin(d_o, d_c);
        if(ob_high == ob_low) { ob_high = d_h; ob_low = d_l; }

        if((ob_high - ob_low) < ob_high * MinOBSizePct) continue;

        // check we don't already have this OB
        datetime ob_time = iTime(_Symbol, PERIOD_M3, impulse_i);
        bool dup = false;
        for(int k = 0; k < OBCount; k++) {
            if(OBZones[k].time == ob_time) { dup = true; break; }
        }
        if(dup) continue;

        if(OBCount >= ArraySize(OBZones)) ArrayResize(OBZones, OBCount + 50);
        OBZones[OBCount].time      = ob_time;
        OBZones[OBCount].direction = direction;
        OBZones[OBCount].ob_high   = ob_high;
        OBZones[OBCount].ob_low    = ob_low;
        OBZones[OBCount].sl_ref    = (direction == -1) ? d_h : d_l;
        OBZones[OBCount].active    = true;
        OBZones[OBCount].triggered = false;
        OBCount++;
    }
}

// ──────────────────────────────────────────────────────────────────
// M1 entry: BB outer band touching OB + EMA200 M1 alignment
// ──────────────────────────────────────────────────────────────────
void CheckOBEntry()
{
    if(CountActiveOrders() >= MaxActiveOrders) return;

    double bb_upper[], bb_lower[], ema1[];
    ArraySetAsSeries(bb_upper, true);
    ArraySetAsSeries(bb_lower, true);
    ArraySetAsSeries(ema1,     true);

    if(CopyBuffer(BbHandleM1, 1, 0, 3, bb_upper) < 3) return;
    if(CopyBuffer(BbHandleM1, 2, 0, 3, bb_lower) < 3) return;
    if(CopyBuffer(EmaHandleM1, 0, 0, 3, ema1)    < 3) return;

    double cur_h    = iHigh (_Symbol, PERIOD_M1, 1);
    double cur_l    = iLow  (_Symbol, PERIOD_M1, 1);
    double cur_c    = iClose(_Symbol, PERIOD_M1, 1);
    double cur_ema1 = ema1[1];
    double cur_bbu  = bb_upper[1];
    double cur_bbl  = bb_lower[1];
    datetime cur_t  = iTime(_Symbol, PERIOD_M1, 1);

    for(int i = 0; i < OBCount; i++) {
        if(!OBZones[i].active || OBZones[i].triggered) continue;

        // expiry check
        int bars_since = (int)((cur_t - OBZones[i].time) / 60);
        if(bars_since > OBExpiryBars) { OBZones[i].active = false; continue; }

        int dir = OBZones[i].direction;
        double ob_h = OBZones[i].ob_high;
        double ob_l = OBZones[i].ob_low;

        // EMA200 M1 alignment
        if(dir == -1 && cur_c > cur_ema1) continue;
        if(dir ==  1 && cur_c < cur_ema1) continue;

        if(dir == -1) {
            if(cur_h < ob_h) continue;   // price must reach the zone
            double tol = ob_h * BbTouchTol;
            if(!(cur_bbu >= ob_l - tol && cur_bbu <= ob_h * (1.0 + BbTouchTol))) continue;
        } else {
            if(cur_l > ob_l) continue;
            double tol = ob_l * BbTouchTol;
            if(!(cur_bbl >= ob_l * (1.0 - BbTouchTol) && cur_bbl <= ob_h + tol)) continue;
        }

        PlaceTrade(OBZones[i]);
        OBZones[i].triggered = true;
        OBZones[i].active    = false;
    }
}

// ──────────────────────────────────────────────────────────────────
// Place two pending limit orders (T1 + T2)
// ──────────────────────────────────────────────────────────────────
void PlaceTrade(OBZone &ob)
{
    int    dir   = ob.direction;
    double entry = (dir == -1) ? ob.ob_high : ob.ob_low;
    double buf   = (ob.ob_high - ob.ob_low) * SLBufferPct;
    double sl    = (dir == -1) ? ob.sl_ref + buf : ob.sl_ref - buf;
    double risk  = MathAbs(entry - sl);
    if(risk == 0) return;

    double tp1   = (dir == -1) ? entry - risk * TP1_RR : entry + risk * TP1_RR;
    double tp2   = (dir == -1) ? entry - risk * TP2_RR : entry + risk * TP2_RR;

    double bal   = AccountInfoDouble(ACCOUNT_BALANCE);
    double tickV = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
    double tickS = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
    double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
    double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
    double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

    if(tickV == 0 || tickS == 0) return;
    double riskMoney = bal * RiskPercent / 100.0;
    double lotRaw    = riskMoney / (risk / tickS * tickV);
    double lot       = MathFloor(lotRaw / lotStep) * lotStep;
    lot = MathMax(minLot, MathMin(maxLot, lot));

    double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
    double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

    if(dir == -1) {
        // bearish: sell limit above current price
        if(entry <= bid) return;
        Trade.SellLimit(lot, entry, _Symbol, sl, tp1, ORDER_TIME_GTC, 0, "OB T1");
        Trade.SellLimit(lot, entry, _Symbol, sl, tp2, ORDER_TIME_GTC, 0, "OB T2");
    } else {
        // bullish: buy limit below current price
        if(entry >= ask) return;
        Trade.BuyLimit(lot, entry, _Symbol, sl, tp1, ORDER_TIME_GTC, 0, "OB T1");
        Trade.BuyLimit(lot, entry, _Symbol, sl, tp2, ORDER_TIME_GTC, 0, "OB T2");
    }
}

// ──────────────────────────────────────────────────────────────────
// ATR trailing stop on T2 position after T1 hits
// ──────────────────────────────────────────────────────────────────
void ManageTrailingStop()
{
    double atr[];
    ArraySetAsSeries(atr, true);
    if(CopyBuffer(AtrHandleM1, 0, 0, 3, atr) < 3) return;
    double trailDist = atr[1] * AtrMultiplier;

    for(int i = PositionsTotal() - 1; i >= 0; i--) {
        if(!PositionSelectByTicket(PositionGetTicket(i))) continue;
        if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
        if(PositionGetString(POSITION_COMMENT) != "OB T2") continue;

        double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
        double cur_sl     = PositionGetDouble(POSITION_SL);
        double cur_tp     = PositionGetDouble(POSITION_TP);
        int    pos_type   = (int)PositionGetInteger(POSITION_TYPE);
        double bid        = SymbolInfoDouble(_Symbol, SYMBOL_BID);
        double ask        = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

        if(pos_type == POSITION_TYPE_BUY) {
            double new_sl = bid - trailDist;
            // only trail if we're in profit (above open) and new SL is higher
            if(bid > open_price && new_sl > cur_sl)
                Trade.PositionModify(PositionGetTicket(i), new_sl, cur_tp);
        } else {
            double new_sl = ask + trailDist;
            if(ask < open_price && new_sl < cur_sl)
                Trade.PositionModify(PositionGetTicket(i), new_sl, cur_tp);
        }
    }
}

// ──────────────────────────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────────────────────────
int CountActiveOrders()
{
    int cnt = 0;
    for(int i = OrdersTotal() - 1; i >= 0; i--) {
        ulong ticket = OrderGetTicket(i);
        if(OrderSelect(ticket) && OrderGetInteger(ORDER_MAGIC) == MagicNumber)
            cnt++;
    }
    for(int i = PositionsTotal() - 1; i >= 0; i--) {
        ulong ticket = PositionGetTicket(i);
        if(PositionSelectByTicket(ticket) && PositionGetInteger(POSITION_MAGIC) == MagicNumber)
            cnt++;
    }
    return cnt;
}

bool IsSession()
{
    if(!UseSessionFilter) return true;
    MqlDateTime dt;
    TimeToStruct(TimeGMT(), dt);
    return (dt.hour >= SessionStartUTC && dt.hour < SessionEndUTC);
}

bool IsWeekend()
{
    if(!UseWeekendFilter) return false;
    MqlDateTime dt;
    TimeToStruct(TimeGMT(), dt);
    if(dt.day_of_week == 6) return true;  // Saturday
    if(dt.day_of_week == 0) return true;  // Sunday
    if(dt.day_of_week == 5 && dt.hour >= FridayCloseHour) return true;
    return false;
}

// ──────────────────────────────────────────────────────────────────
// Info panel
// ──────────────────────────────────────────────────────────────────
void DrawPanel()
{
    int active_ob = 0;
    for(int i = 0; i < OBCount; i++)
        if(OBZones[i].active) active_ob++;

    double bal = AccountInfoDouble(ACCOUNT_BALANCE);
    double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
    double dd  = (DayStartBalance - MathMin(bal, eq)) / DayStartBalance * 100.0;

    string lines[6];
    lines[0] = "Order Block EA";
    lines[1] = StringFormat("Active OBs   : %d", active_ob);
    lines[2] = StringFormat("Open orders  : %d", CountActiveOrders());
    lines[3] = StringFormat("Daily DD     : %.2f%%", dd);
    lines[4] = StringFormat("Balance      : %.2f", bal);
    lines[5] = DailyDDBreached() ? ">> DD LIMIT — HALTED <<" : "Running";

    int x = 10, y = 20, lh = 18;
    for(int i = 0; i < 6; i++) {
        string name = "OB_Panel_" + IntegerToString(i);
        if(ObjectFind(0, name) < 0)
            ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
        ObjectSetInteger(0, name, OBJPROP_CORNER,    CORNER_LEFT_UPPER);
        ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
        ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y + i * lh);
        ObjectSetInteger(0, name, OBJPROP_COLOR,     i == 5 && DailyDDBreached() ? clrRed : clrWhite);
        ObjectSetInteger(0, name, OBJPROP_FONTSIZE,  9);
        ObjectSetString (0, name, OBJPROP_TEXT,      lines[i]);
        ObjectSetString (0, name, OBJPROP_FONT,      "Courier New");
    }
    ChartRedraw();
}

void DeletePanel()
{
    for(int i = 0; i < 6; i++)
        ObjectDelete(0, "OB_Panel_" + IntegerToString(i));
}
