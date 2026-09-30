"""Universo di asset selezionabili, divisi per categoria.

Ogni asset e' identificato dal ticker Yahoo Finance. Dove possibile sono stati
scelti strumenti con storico lungo (>= 20 anni). Per le obbligazioni si usano
anche fondi comuni storici (Vanguard/PIMCO) che coprono tutto il periodo.
"""
from __future__ import annotations

from dataclasses import dataclass

ETF = "ETF"
STOCK = "Azioni"
BOND = "Obbligazioni"
COMMODITY = "Materie prime"

CATEGORIES = [ETF, STOCK, BOND, COMMODITY]

CATEGORY_COLORS = {
    ETF: "#4F8CFF",
    STOCK: "#FF6B8B",
    BOND: "#2ED3A0",
    COMMODITY: "#FFB547",
}


@dataclass(frozen=True)
class Asset:
    ticker: str
    name: str
    category: str

    @property
    def currency(self) -> str:
        if self.ticker.endswith((".MI", ".DE", ".PA", ".AS", ".MC", ".F")):
            return "EUR"
        return "USD"


_ETF = [
    ("SPY", "SPDR S&P 500"),
    ("QQQ", "Invesco Nasdaq 100"),
    ("DIA", "SPDR Dow Jones Industrial"),
    ("VTI", "Vanguard Total US Stock Market"),
    ("IWM", "iShares Russell 2000 (small cap)"),
    ("MDY", "SPDR S&P MidCap 400"),
    ("IJR", "iShares S&P SmallCap 600"),
    ("VUG", "Vanguard US Growth"),
    ("VTV", "Vanguard US Value"),
    ("IWF", "iShares Russell 1000 Growth"),
    ("IWD", "iShares Russell 1000 Value"),
    ("VIG", "Vanguard Dividend Appreciation"),
    ("DVY", "iShares Select Dividend"),
    ("EFA", "iShares MSCI EAFE (sviluppati ex-USA)"),
    ("VEA", "Vanguard FTSE Developed Markets"),
    ("EEM", "iShares MSCI Emerging Markets"),
    ("VWO", "Vanguard FTSE Emerging Markets"),
    ("ACWI", "iShares MSCI ACWI (mondo)"),
    ("VT", "Vanguard Total World Stock"),
    ("VGK", "Vanguard FTSE Europe"),
    ("EZU", "iShares MSCI Eurozone"),
    ("EWI", "iShares MSCI Italia"),
    ("EWG", "iShares MSCI Germania"),
    ("EWQ", "iShares MSCI Francia"),
    ("EWU", "iShares MSCI Regno Unito"),
    ("EWL", "iShares MSCI Svizzera"),
    ("EWJ", "iShares MSCI Giappone"),
    ("FXI", "iShares China Large-Cap"),
    ("EWZ", "iShares MSCI Brasile"),
    ("EWT", "iShares MSCI Taiwan"),
    ("EWY", "iShares MSCI Corea del Sud"),
    ("EWA", "iShares MSCI Australia"),
    ("EWC", "iShares MSCI Canada"),
    ("INDA", "iShares MSCI India"),
    ("XLK", "Technology Select Sector"),
    ("XLF", "Financial Select Sector"),
    ("XLV", "Health Care Select Sector"),
    ("XLE", "Energy Select Sector"),
    ("XLI", "Industrial Select Sector"),
    ("XLY", "Consumer Discretionary Select Sector"),
    ("XLP", "Consumer Staples Select Sector"),
    ("XLU", "Utilities Select Sector"),
    ("VNQ", "Vanguard Real Estate (REIT)"),
    ("SMH", "VanEck Semiconductor"),
    ("IBB", "iShares Biotechnology"),
    ("ITA", "iShares US Aerospace & Defense"),
    ("ARKK", "ARK Innovation"),
    ("SWDA.MI", "iShares Core MSCI World (UCITS)"),
    ("CSSPX.MI", "iShares Core S&P 500 (UCITS)"),
    ("VWCE.DE", "Vanguard FTSE All-World Acc (UCITS)"),
]

_STOCK = [
    ("AAPL", "Apple"),
    ("MSFT", "Microsoft"),
    ("AMZN", "Amazon"),
    ("GOOGL", "Alphabet (Google)"),
    ("META", "Meta Platforms"),
    ("NVDA", "NVIDIA"),
    ("TSLA", "Tesla"),
    ("BRK-B", "Berkshire Hathaway"),
    ("JPM", "JPMorgan Chase"),
    ("V", "Visa"),
    ("MA", "Mastercard"),
    ("JNJ", "Johnson & Johnson"),
    ("PG", "Procter & Gamble"),
    ("KO", "Coca-Cola"),
    ("PEP", "PepsiCo"),
    ("WMT", "Walmart"),
    ("COST", "Costco"),
    ("HD", "Home Depot"),
    ("MCD", "McDonald's"),
    ("NKE", "Nike"),
    ("SBUX", "Starbucks"),
    ("DIS", "Walt Disney"),
    ("NFLX", "Netflix"),
    ("ADBE", "Adobe"),
    ("CRM", "Salesforce"),
    ("ORCL", "Oracle"),
    ("INTC", "Intel"),
    ("AMD", "AMD"),
    ("CSCO", "Cisco"),
    ("IBM", "IBM"),
    ("XOM", "ExxonMobil"),
    ("CVX", "Chevron"),
    ("UNH", "UnitedHealth"),
    ("LLY", "Eli Lilly"),
    ("PFE", "Pfizer"),
    ("MRK", "Merck & Co."),
    ("BA", "Boeing"),
    ("CAT", "Caterpillar"),
    ("GS", "Goldman Sachs"),
    ("ASML", "ASML"),
    ("TSM", "TSMC"),
    ("NVO", "Novo Nordisk"),
    ("SAP", "SAP"),
    ("TM", "Toyota"),
    ("MC.PA", "LVMH"),
    ("ENI.MI", "Eni"),
    ("ENEL.MI", "Enel"),
    ("ISP.MI", "Intesa Sanpaolo"),
    ("UCG.MI", "UniCredit"),
    ("RACE.MI", "Ferrari"),
]

_BOND = [
    ("AGG", "iShares Core US Aggregate Bond"),
    ("BND", "Vanguard Total Bond Market ETF"),
    ("VBMFX", "Vanguard Total Bond Market (fondo)"),
    ("TLT", "iShares Treasury 20+ anni"),
    ("IEF", "iShares Treasury 7-10 anni"),
    ("IEI", "iShares Treasury 3-7 anni"),
    ("SHY", "iShares Treasury 1-3 anni"),
    ("SHV", "iShares Treasury < 1 anno"),
    ("BIL", "SPDR T-Bill 1-3 mesi"),
    ("GOVT", "iShares US Treasury Bond"),
    ("VUSTX", "Vanguard Long-Term Treasury (fondo)"),
    ("VFITX", "Vanguard Interm.-Term Treasury (fondo)"),
    ("VFISX", "Vanguard Short-Term Treasury (fondo)"),
    ("EDV", "Vanguard Extended Duration Treasury"),
    ("ZROZ", "PIMCO 25+ Year Zero Coupon"),
    ("TIP", "iShares TIPS (inflation-linked)"),
    ("VIPSX", "Vanguard Inflation-Protected (fondo)"),
    ("STIP", "iShares 0-5 Year TIPS"),
    ("SCHP", "Schwab US TIPS"),
    ("LQD", "iShares Investment Grade Corporate"),
    ("VCIT", "Vanguard Interm.-Term Corporate"),
    ("VCSH", "Vanguard Short-Term Corporate"),
    ("VWESX", "Vanguard Long-Term Inv. Grade (fondo)"),
    ("IGSB", "iShares 1-5 Year IG Corporate"),
    ("HYG", "iShares High Yield Corporate"),
    ("JNK", "SPDR High Yield Bond"),
    ("VWEHX", "Vanguard High-Yield Corporate (fondo)"),
    ("SJNK", "SPDR Short-Term High Yield"),
    ("ANGL", "VanEck Fallen Angel High Yield"),
    ("EMB", "iShares JPM USD Emerging Markets Bond"),
    ("PCY", "Invesco Emerging Markets Sovereign"),
    ("VWOB", "Vanguard Emerging Markets Gov. Bond"),
    ("BWX", "SPDR International Treasury"),
    ("IGOV", "iShares International Treasury"),
    ("BNDX", "Vanguard Total International Bond"),
    ("MUB", "iShares National Muni Bond"),
    ("MBB", "iShares MBS (mutui)"),
    ("BSV", "Vanguard Short-Term Bond"),
    ("BIV", "Vanguard Intermediate-Term Bond"),
    ("BLV", "Vanguard Long-Term Bond"),
    ("SCHZ", "Schwab US Aggregate Bond"),
    ("FLOT", "iShares Floating Rate Bond"),
    ("BKLN", "Invesco Senior Loan"),
    ("CWB", "SPDR Convertible Securities"),
    ("PFF", "iShares Preferred & Income"),
    ("PTTRX", "PIMCO Total Return (fondo)"),
    ("FXNAX", "Fidelity US Bond Index (fondo)"),
    ("VGIT", "Vanguard Interm.-Term Treasury ETF"),
    ("VGLT", "Vanguard Long-Term Treasury ETF"),
    ("VGSH", "Vanguard Short-Term Treasury ETF"),
]

_COMMODITY = [
    ("GC=F", "Oro (future)"),
    ("SI=F", "Argento (future)"),
    ("HG=F", "Rame (future)"),
    ("PL=F", "Platino (future)"),
    ("PA=F", "Palladio (future)"),
    ("GLD", "SPDR Gold Shares"),
    ("IAU", "iShares Gold Trust"),
    ("SLV", "iShares Silver Trust"),
    ("PPLT", "abrdn Platinum"),
    ("PALL", "abrdn Palladium"),
    ("CPER", "US Copper Index Fund"),
    ("USO", "United States Oil Fund (petrolio WTI)"),
    ("BNO", "United States Brent Oil"),
    ("UNG", "United States Natural Gas"),
    ("DBC", "Invesco DB Commodity Index"),
    ("GSG", "iShares S&P GSCI Commodity"),
    ("PDBC", "Invesco Optimum Yield Diversified"),
    ("DBA", "Invesco DB Agriculture"),
    ("DBB", "Invesco DB Base Metals"),
    ("DBO", "Invesco DB Oil"),
    ("DBE", "Invesco DB Energy"),
    ("DBP", "Invesco DB Precious Metals"),
    ("SIVR", "abrdn Silver ETF"),
    ("SGOL", "abrdn Gold ETF"),
    ("CORN", "Teucrium Corn (mais)"),
    ("WEAT", "Teucrium Wheat (grano)"),
    ("SOYB", "Teucrium Soybean (soia)"),
    ("CANE", "Teucrium Sugar (zucchero)"),
    ("ZC=F", "Mais (future)"),
    ("ZW=F", "Grano (future)"),
    ("ZS=F", "Soia (future)"),
    ("KC=F", "Caffe' (future)"),
    ("CC=F", "Cacao (future)"),
    ("SB=F", "Zucchero (future)"),
    ("CT=F", "Cotone (future)"),
    ("LE=F", "Bovini vivi (future)"),
    ("HE=F", "Suini magri (future)"),
    ("NG=F", "Gas naturale (future)"),
    ("BZ=F", "Petrolio Brent (future)"),
    ("GDX", "VanEck Gold Miners"),
    ("GDXJ", "VanEck Junior Gold Miners"),
    ("SIL", "Global X Silver Miners"),
    ("COPX", "Global X Copper Miners"),
    ("XME", "SPDR Metals & Mining"),
    ("PICK", "iShares MSCI Global Metals & Mining"),
    ("URA", "Global X Uranium"),
    ("LIT", "Global X Lithium & Battery"),
    ("REMX", "VanEck Rare Earth/Strategic Metals"),
    ("WOOD", "iShares Global Timber & Forestry"),
    ("MOO", "VanEck Agribusiness"),
]


def _build() -> list[Asset]:
    out: list[Asset] = []
    for cat, rows in ((ETF, _ETF), (STOCK, _STOCK), (BOND, _BOND), (COMMODITY, _COMMODITY)):
        out.extend(Asset(t, n, cat) for t, n in rows)
    return out


ASSETS: list[Asset] = _build()
BY_TICKER: dict[str, Asset] = {a.ticker: a for a in ASSETS}

FX_TICKER = "EURUSD=X"
