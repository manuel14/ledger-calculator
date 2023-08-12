from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime

@dataclass
class Advance:
    id: int = None
    type: str = None
    initial_amount: Decimal = None
    date: datetime = None
    current_amount: Decimal = None
    last_modified_date: datetime = None
    