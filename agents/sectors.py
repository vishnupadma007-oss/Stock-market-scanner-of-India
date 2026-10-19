"""Which sector index each stock belongs to, and which stocks move with crude oil or the rupee.

crude: +1 = gains when crude rises (producers), -1 = hurt when crude rises (fuel/raw-material users).
rupee: +1 = gains when the rupee weakens (exporters: IT, pharma).
"""

SECTORS = {
    # name: (INDmoney ind_key, Yahoo ticker)
    "IT": ("INDI00028", "^CNXIT"),
    "Bank": ("INDI00024", "^NSEBANK"),
    "PSU Bank": ("INDI00312", "^CNXPSUBANK"),
    "Auto": ("INDI00245", "^CNXAUTO"),
    "Pharma": ("INDI00031", "^CNXPHARMA"),
    "Metal": ("INDI00247", "^CNXMETAL"),
    "Energy": ("INDI00220", "^CNXENERGY"),
    "FMCG": ("INDI00235", "^CNXFMCG"),
    "Realty": ("INDI00329", "^CNXREALTY"),
    "Market": ("INDI00012", "^NSEI"),  # stocks without a closer sector index
}

STOCK_SECTOR = {
    **dict.fromkeys(["INFY", "TCS", "WIPRO", "HCLTECH", "TECHM", "PERSISTENT", "COFORGE", "MPHASIS"], "IT"),
    **dict.fromkeys(["HDFCBANK", "ICICIBANK", "AXISBANK", "KOTAKBANK", "INDUSINDBK", "IDFCFIRSTB",
                     "FEDERALBNK", "AUBANK", "BAJFINANCE", "BAJFINSV", "SHRIRAMFIN", "CHOLAFIN",
                     "MUTHOOTFIN", "RECLTD", "PFC", "PAYTM", "POLICYBZR"], "Bank"),
    **dict.fromkeys(["SBIN", "BANKBARODA", "PNB", "CANBK"], "PSU Bank"),
    **dict.fromkeys(["MARUTI", "M&M", "EICHERMOT", "HEROMOTOCO", "BAJAJ-AUTO", "TVSMOTOR"], "Auto"),
    **dict.fromkeys(["SUNPHARMA", "CIPLA", "DRREDDY", "DIVISLAB", "LUPIN", "APOLLOHOSP"], "Pharma"),
    **dict.fromkeys(["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "SAIL", "NMDC", "NATIONALUM",
                     "COALINDIA", "ADANIENT"], "Metal"),
    **dict.fromkeys(["RELIANCE", "ONGC", "NTPC", "POWERGRID", "BPCL", "IOC", "GAIL", "TATAPOWER"], "Energy"),
    **dict.fromkeys(["ITC", "HINDUNILVR", "NESTLEIND", "BRITANNIA"], "FMCG"),
    "DLF": "Realty",
}

CRUDE_SENSITIVITY = {"ONGC": 1, "BPCL": -1, "IOC": -1, "ASIANPAINT": -1}
RUPEE_SENSITIVITY = {s: 1 for s, sec in STOCK_SECTOR.items() if sec in ("IT", "Pharma")}


def sector_of(symbol: str) -> str:
    return STOCK_SECTOR.get(symbol, "Market")
