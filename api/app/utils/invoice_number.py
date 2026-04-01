from sqlalchemy import text
from sqlalchemy.orm import Session


def generate_invoice_number(
    db: Session,
    pos_opening_entry_id: int,
    opening_entry_name: str,
) -> str:
    """Atomically generate the next invoice number for a POS opening entry.

    Uses SELECT ... FOR UPDATE to lock the sequence row, ensuring no two
    concurrent transactions can get the same number.

    Returns a string like 'POS-POS-OPEN-00001-00001'.
    """
    # Try to get and lock existing sequence row
    row = db.execute(
        text(
            "SELECT id, last_sequence FROM pos_invoice_sequence "
            "WHERE pos_opening_entry_id = :oe_id FOR UPDATE"
        ),
        {"oe_id": pos_opening_entry_id},
    ).fetchone()

    if row is None:
        # First invoice for this opening entry — insert sequence row
        db.execute(
            text(
                "INSERT INTO pos_invoice_sequence (pos_opening_entry_id, last_sequence) "
                "VALUES (:oe_id, 1)"
            ),
            {"oe_id": pos_opening_entry_id},
        )
        new_seq = 1
    else:
        new_seq = row.last_sequence + 1
        db.execute(
            text(
                "UPDATE pos_invoice_sequence SET last_sequence = :seq "
                "WHERE id = :row_id"
            ),
            {"seq": new_seq, "row_id": row.id},
        )

    return f"POS-{opening_entry_name}-{new_seq:05d}"
