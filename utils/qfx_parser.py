"""
QFX / OFX parser for Chase and other banks.
Uses ofxparse.
"""
from ofxparse import OfxParser
from datetime import datetime
import io

def parse_qfx(file_bytes: bytes) -> list[dict]:
    """
    Parse a QFX/OFX file and return a list of transaction dicts.
    Each dict: date, description, amount, fitid, type
    """
    try:
        ofx = OfxParser.parse(io.BytesIO(file_bytes))
    except Exception as e:
        raise ValueError(f"Could not parse QFX/OFX file: {e}")

    transactions = []
    account = ofx.account
    if not account or not account.statement:
        return transactions

    for txn in account.statement.transactions:
        amount = float(txn.amount)

        desc_parts = []
        if txn.payee:
            desc_parts.append(str(txn.payee).strip())
        if txn.memo:
            memo = str(txn.memo).strip()
            if memo and memo not in desc_parts:
                desc_parts.append(memo)
        description = " | ".join(desc_parts) if desc_parts else (txn.type or "Transaction")

        date_str = txn.date.strftime("%Y-%m-%d") if txn.date else None
        fitid = str(txn.id).strip() if txn.id else None

        transactions.append({
            "date": date_str,
            "description": description[:500],
            "amount": amount,
            "fitid": fitid,
            "type": str(txn.type) if txn.type else "",
            "source": "qfx"
        })

    transactions.sort(key=lambda x: x["date"] or "", reverse=True)
    return transactions
