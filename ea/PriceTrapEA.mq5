//+------------------------------------------------------------------+
//|  PriceTrapEA.mq5  —  Price Trap Strategy                        |
//|  H1 range breakout + M15 engulfing + Fibonacci limit entry      |
//+------------------------------------------------------------------+
#property copyright "Price Trap EA"
#property version   "1.01"

#include <Trade\Trade.mqh>

// ── Strategy ──────────────────────────────────────────────────────
input group "Strategy"
input int    RangeMinPips    = 20;
input int    RangeMaxPips    = 30;
input int    RangeLookback   = 12;
input int    MinRangeCandles = 4;
input double RangeBodyPct    = 0.60;
input double FiboEntry       = 0.618;
input double FiboSLExt       = 0.786;
input double TP1_RR          = 2.0;
input double TP2_RR          = 4.0;
input int    MinEngulfPips   = 3;
input int    EngulfBars      = 12;   // M15 bars to search for engulfing after breakout
input int    LimitExpiry     = 16;   // M15 bars limit order stays open
input bool   UseTrendFilter  = true;

// ── Risk ──────────────────────────────────────────────────────────
input group "Risk"
input double RiskPercent     = 1.0;  // % risk per leg (2 legs per setup)
input int    MaxActiveSetups = 5;
input long   MagicNumber     = 20240101;

// ── Session ───────────────────────────────────────────────────────
input group "Session"
input int    SessionStartUTC = 7;
input int    SessionEndUTC   = 21;

// ── News Filter ───────────────────────────────────────────────────
input group "News Filter"
input bool   UseNewsFilter   = true;
input int    NewsMinsBefore  = 30;
input int    NewsMinsAfter   = 30;

// ── Weekend Filter ────────────────────────────────────────────────
input group "Weekend Filter"
input bool   UseWeekendFilter = true;
input int    FridayCloseHour = 21;

//──────────────────────────────────────────────────────────────────
CTrade   Trade;
int      EmaHandle  = INVALID_HANDLE;
datetime LastM15Bar = 0;
datetime LastH1Bar  = 0;

//+------------------------------------------------------------------+
int OnInit()
{
    Trade.SetExpertMagicNumber(MagicNumber);
    Trade.SetDeviationInPoints(10);
    EmaHandle = iMA(_Symbol, PERIOD_D1, 50, 0, MODE_EMA, PRICE_CLOSE);
    return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
    if(EmaHandle != INVALID_HANDLE) IndicatorRelease(EmaHandle);
}

//+------------------------------------------------------------------+
void OnTick()
{
    if(UseWeekendFilter && IsWeekendTime()) { CloseAll(); return; }

    ManageBreakeven();

    datetime curM15 = iTime(_Symbol, PERIOD_M15, 0);
    datetime curH1  = iTime(_Symbol, PERIOD_H1,  0);

    if(curM15 != LastM15Bar) { LastM15Bar = curM15; OnNewM15(); }
    if(curH1  != LastH1Bar)  { LastH1Bar  = curH1;  }
}

//+------------------------------------------------------------------+
// On every new M15 bar: scan recent H1 bars for breakout,
// check if current M15[1] is the engulfing candle.
//+------------------------------------------------------------------+
void OnNewM15()
{
    if(CountSetups() >= MaxActiveSetups) return;
    if(UseNewsFilter && IsNewsTime())    return;

    MqlDateTime dt;
    TimeToStruct(TimeCurrent(), dt);
    if(dt.hour < SessionStartUTC || dt.hour >= SessionEndUTC) return;
    if(UseWeekendFilter && dt.day_of_week == 5 && dt.hour >= FridayCloseHour) return;

    double pip     = PipSize();
    double minBody = MinEngulfPips * pip;

    // M15 bar 1 = just-closed candle (potential engulfing)
    double co = iOpen(_Symbol,  PERIOD_M15, 1);
    double cc = iClose(_Symbol, PERIOD_M15, 1);
    double po = iOpen(_Symbol,  PERIOD_M15, 2);
    double pc = iClose(_Symbol, PERIOD_M15, 2);

    double cBH = MathMax(co,cc), cBL = MathMin(co,cc);
    double pBH = MathMax(po,pc), pBL = MathMin(po,pc);
    double cBody = cBH - cBL;
    double pBody = pBH - pBL;
    if(cBody < minBody) return;

    datetime engTime = iTime(_Symbol, PERIOD_M15, 1);

    // Scan last few H1 bars for a breakout that this M15 bar could follow
    int maxH1Back = EngulfBars / 4 + 2;
    for(int hi = 1; hi <= maxH1Back; hi++)
    {
        datetime h1Time = iTime(_Symbol, PERIOD_H1, hi);

        // Engulfing must be after the breakout H1 bar opened
        if(engTime <= h1Time) continue;

        // Engulfing must be within EngulfBars M15 candles of breakout
        int brkM15Idx = iBarShift(_Symbol, PERIOD_M15, h1Time, false);
        int engM15Idx = iBarShift(_Symbol, PERIOD_M15, engTime, false);
        int m15Dist   = brkM15Idx - engM15Idx;
        if(m15Dist < 1 || m15Dist > EngulfBars) continue;

        // Detect range before this H1 bar
        double rHigh, rLow;
        if(!DetectRangeAt(hi + 1, pip, rHigh, rLow)) continue;

        // Check if that H1 bar broke the range
        int dir = BreakoutDir(hi, rHigh, rLow);
        if(dir == 0) continue;

        // D1 trend filter
        if(UseTrendFilter)
        {
            int trend = D1TrendDir();
            if(trend != 0 && trend != dir) continue;
        }

        // Check engulfing direction
        bool ok = false;
        if(dir == -1 && cc < co && cc < pBL && cBody > pBody) ok = true; // bearish
        if(dir ==  1 && cc > co && cc > pBH && cBody > pBody) ok = true; // bullish
        if(!ok) continue;

        // Skip if we already have an order near this entry
        double entry, sl;
        if(!FiboLevels(co, cc, dir, entry, sl)) continue;

        double risk = MathAbs(entry - sl);
        if(risk == 0) continue;

        if(DuplicateEntry(entry)) continue;

        double tp1 = (dir == -1) ? entry - risk*TP1_RR : entry + risk*TP1_RR;
        double tp2 = (dir == -1) ? entry - risk*TP2_RR : entry + risk*TP2_RR;
        double lot = LotSize(risk);
        if(lot <= 0) continue;

        datetime expiry = engTime + LimitExpiry * 15 * 60;
        string   tag    = DoubleToString(entry, _Digits);

        if(dir == -1)
        {
            Trade.SellLimit(lot, entry, _Symbol, sl, tp1, ORDER_TIME_SPECIFIED, expiry, "PT_T1_"+tag);
            Trade.SellLimit(lot, entry, _Symbol, sl, tp2, ORDER_TIME_SPECIFIED, expiry, "PT_T2_"+tag);
        }
        else
        {
            Trade.BuyLimit(lot, entry, _Symbol, sl, tp1, ORDER_TIME_SPECIFIED, expiry, "PT_T1_"+tag);
            Trade.BuyLimit(lot, entry, _Symbol, sl, tp2, ORDER_TIME_SPECIFIED, expiry, "PT_T2_"+tag);
        }
        break; // one setup per M15 bar
    }
}

//+------------------------------------------------------------------+
bool DetectRangeAt(int startIdx, double pip, double &rHigh, double &rLow)
{
    int endIdx  = startIdx + RangeLookback;
    int h1Bars  = iBars(_Symbol, PERIOD_H1);
    if(endIdx >= h1Bars) return false;

    rHigh = -DBL_MAX;
    rLow  =  DBL_MAX;
    int count = 0;
    for(int i = startIdx; i < endIdx; i++, count++)
    {
        double h = iHigh(_Symbol, PERIOD_H1, i);
        double l = iLow(_Symbol,  PERIOD_H1, i);
        if(h > rHigh) rHigh = h;
        if(l < rLow)  rLow  = l;
    }
    if(count < MinRangeCandles) return false;

    double spread = rHigh - rLow;
    if(spread < RangeMinPips * pip || spread > RangeMaxPips * pip) return false;

    int inside = 0;
    for(int i = startIdx; i < endIdx; i++)
    {
        double o = iOpen(_Symbol,  PERIOD_H1, i);
        double c = iClose(_Symbol, PERIOD_H1, i);
        if(MathMin(o,c) >= rLow && MathMax(o,c) <= rHigh) inside++;
    }
    if((double)inside / count < RangeBodyPct) return false;

    int nearHigh = 0, nearLow = 0;
    for(int i = startIdx; i < endIdx; i++)
    {
        if(iHigh(_Symbol, PERIOD_H1, i) >= rHigh - 3*pip) nearHigh++;
        if(iLow(_Symbol,  PERIOD_H1, i) <= rLow  + 3*pip) nearLow++;
    }
    return (nearHigh >= 1 && nearLow >= 1);
}

// Returns 1=up, -1=down, 0=none
int BreakoutDir(int h1Idx, double rHigh, double rLow)
{
    double o  = iOpen(_Symbol,  PERIOD_H1, h1Idx);
    double c  = iClose(_Symbol, PERIOD_H1, h1Idx);
    double bH = MathMax(o,c), bL = MathMin(o,c);
    if(bH == bL)   return 0;
    if(bL > rHigh) return 1;
    if(bH < rLow)  return -1;
    return 0;
}

bool FiboLevels(double open, double close, int dir, double &entry, double &sl)
{
    double bH = MathMax(open,close), bL = MathMin(open,close);
    double sz = bH - bL;
    if(sz == 0) return false;
    if(dir == -1) { entry = bH - FiboEntry*sz; sl = bH + FiboSLExt*sz; }
    else          { entry = bL + FiboEntry*sz; sl = bL - FiboSLExt*sz; }
    return true;
}

// Returns 1=up, -1=down, 0=unknown
int D1TrendDir()
{
    if(EmaHandle == INVALID_HANDLE) return 0;
    double ema[];
    ArraySetAsSeries(ema, true);
    if(CopyBuffer(EmaHandle, 0, 1, 1, ema) <= 0) return 0;
    double c = iClose(_Symbol, PERIOD_D1, 1);
    return (c > ema[0]) ? 1 : -1;
}

double LotSize(double riskPrice)
{
    double money = AccountInfoDouble(ACCOUNT_BALANCE) * RiskPercent / 100.0;
    double tv    = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
    double ts    = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
    if(ts == 0 || tv == 0) return 0;
    double lots  = money / (riskPrice / ts * tv);
    double step  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
    double minL  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
    double maxL  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
    lots = MathFloor(lots / step) * step;
    return MathMax(minL, MathMin(maxL, lots));
}

bool DuplicateEntry(double entry)
{
    double tol = PipSize() * 2;
    for(int i = OrdersTotal()-1; i >= 0; i--)
    {
        ulong t = OrderGetTicket(i);
        if(!t) continue;
        if(OrderGetInteger(ORDER_MAGIC) != MagicNumber) continue;
        if(OrderGetString(ORDER_SYMBOL) != _Symbol)     continue;
        if(MathAbs(OrderGetDouble(ORDER_PRICE_OPEN) - entry) < tol) return true;
    }
    return false;
}

//+------------------------------------------------------------------+
// Move T2 SL to breakeven once T1 has closed (hit TP1)
//+------------------------------------------------------------------+
void ManageBreakeven()
{
    double pip = PipSize();
    double tol = pip * 0.5;

    for(int i = PositionsTotal()-1; i >= 0; i--)
    {
        ulong ticket = PositionGetTicket(i);
        if(!ticket) continue;
        if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
        if(PositionGetString(POSITION_SYMBOL) != _Symbol)     continue;

        string comment = PositionGetString(POSITION_COMMENT);
        if(StringFind(comment, "PT_T2_") < 0) continue;

        double entryPx  = StringToDouble(StringSubstr(comment, 6));
        if(entryPx == 0) continue;

        double curSL = PositionGetDouble(POSITION_SL);
        if(MathAbs(curSL - entryPx) < _Point * 2) continue; // already at BE

        if(!T1Alive(entryPx, tol))
            Trade.PositionModify(ticket, entryPx, PositionGetDouble(POSITION_TP));
    }
}

bool T1Alive(double entryPx, double tol)
{
    for(int j = PositionsTotal()-1; j >= 0; j--)
    {
        if(!PositionGetTicket(j)) continue;
        if(PositionGetInteger(POSITION_MAGIC) != MagicNumber) continue;
        if(PositionGetString(POSITION_SYMBOL) != _Symbol)     continue;
        string c = PositionGetString(POSITION_COMMENT);
        if(StringFind(c,"PT_T1_") >= 0 &&
           MathAbs(StringToDouble(StringSubstr(c,6))-entryPx) < tol) return true;
    }
    for(int j = OrdersTotal()-1; j >= 0; j--)
    {
        ulong ot = OrderGetTicket(j);
        if(!ot) continue;
        if(OrderGetInteger(ORDER_MAGIC) != MagicNumber) continue;
        if(OrderGetString(ORDER_SYMBOL) != _Symbol)     continue;
        string c = OrderGetString(ORDER_COMMENT);
        if(StringFind(c,"PT_T1_") >= 0 &&
           MathAbs(StringToDouble(StringSubstr(c,6))-entryPx) < tol) return true;
    }
    return false;
}

int CountSetups()
{
    int n = 0;
    for(int i = PositionsTotal()-1; i >= 0; i--)
    {
        ulong t = PositionGetTicket(i);
        if(t && PositionGetInteger(POSITION_MAGIC)==MagicNumber
             && PositionGetString(POSITION_SYMBOL)==_Symbol) n++;
    }
    for(int i = OrdersTotal()-1; i >= 0; i--)
    {
        ulong t = OrderGetTicket(i);
        if(t && OrderGetInteger(ORDER_MAGIC)==MagicNumber
             && OrderGetString(ORDER_SYMBOL)==_Symbol) n++;
    }
    return (n + 1) / 2;
}

bool IsNewsTime()
{
    MqlCalendarValue vals[];
    datetime from = TimeCurrent() - NewsMinsBefore*60;
    datetime to   = TimeCurrent() + NewsMinsAfter *60;
    if(CalendarValueHistory(vals, from, to, NULL, _Symbol) <= 0) return false;
    for(int i = 0; i < ArraySize(vals); i++)
    {
        MqlCalendarEvent ev;
        if(CalendarEventById(vals[i].event_id, ev) &&
           ev.importance == CALENDAR_IMPORTANCE_HIGH) return true;
    }
    return false;
}

bool IsWeekendTime()
{
    MqlDateTime dt;
    TimeToStruct(TimeCurrent(), dt);
    return (dt.day_of_week == 6 || dt.day_of_week == 0 ||
           (dt.day_of_week == 5 && dt.hour >= FridayCloseHour));
}

void CloseAll()
{
    for(int i = PositionsTotal()-1; i >= 0; i--)
    {
        ulong t = PositionGetTicket(i);
        if(t && PositionGetInteger(POSITION_MAGIC)==MagicNumber
             && PositionGetString(POSITION_SYMBOL)==_Symbol)
            Trade.PositionClose(t);
    }
    for(int i = OrdersTotal()-1; i >= 0; i--)
    {
        ulong t = OrderGetTicket(i);
        if(t && OrderGetInteger(ORDER_MAGIC)==MagicNumber
             && OrderGetString(ORDER_SYMBOL)==_Symbol)
            Trade.OrderDelete(t);
    }
}

double PipSize()
{
    return (StringFind(_Symbol,"JPY") >= 0) ? 0.01 : 0.0001;
}
