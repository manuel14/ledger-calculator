from datetime import datetime, timedelta
from decimal import Decimal
from typing import Iterable, Tuple

from advance import Advance

class AdvanceStats:
    """
    This class takes care of calculating the neccesary statistics for each advance
    and also the summry for all advances
    """
    ADVANCE_INTEREST_RATE = Decimal(0.00035)
    PAYMENT_EVENT = "payment"
    ADVANCE_EVENT = "advance"

    def __init__(self) -> None:
        self.overall_advance_balance = Decimal(0)
        self.overall_interest_payable_balance = Decimal(0)
        self.overall_interest_paid = Decimal(0)
        self.overall_payments_for_future = Decimal(0)
        self.advances = []
        # when an advance is fully paid we increase this index to not reprocess an advance
        # when deducting advances and calculating overall interest
        self.first_not_fully_paid_advance_index = 0
       
    def get_overall_interest(self, end_datetime: datetime) -> Decimal:
        """
        Calculates what's the overall interest value according to the date passed as argument
        Basically is just a sum of the delta between last date an advance was modified and the
        event date * ADVANCE_INTEREST_RATE * advance current amount
        """
        total_interest = 0
        for advance in self.advances[self.first_not_fully_paid_advance_index:]:
            advance_datetime = advance.last_modified_date
            advance_amount = advance.current_amount
            if advance_datetime > end_datetime or advance_amount == 0:
                continue
            advance_interest_days = ((end_datetime - advance_datetime).days)
            if advance_interest_days == 0:
                continue
            total_interest += (advance_amount * Decimal(self.ADVANCE_INTEREST_RATE) * advance_interest_days)
        return total_interest

    def reduce_advances(self, amount: Decimal, event_datetime: datetime) -> None:
        """
        Takes care of deducting all advances possible based on the remaining amount obtained
        after paying overall_interest_payable_balance
        """
        remaining = Decimal(amount)
        # we start from last not fully paid advance
        advance_index = self.first_not_fully_paid_advance_index
        while remaining > 0:
            try:
                advance = self.advances[advance_index]
                advance_amount = advance.current_amount
            except IndexError:
                # no more advances to pay, so overall_payments_for_future will be increased
                break
            remaining_acc = remaining - advance_amount
            if remaining > advance.current_amount:
                advance.current_amount = 0
                # advance fully paid so we don't need to try to deduct it next time a payment comes in
                self.first_not_fully_paid_advance_index += 1
            else:
                advance.current_amount -= remaining
            
            advance.last_modified_date = event_datetime
            remaining = remaining_acc
            advance_index += 1
            
        for advance in self.advances[advance_index:]:
            # advances whose values where not deducted still need to reset interest date to current
            # event datetime
            advance.last_modified_date = event_datetime


    def process_advance(self, advance: Advance) -> None:
        """
        Process advance, taking into account if there is any self.overall_payments_for_future
        and adds them to the list of advances
        """
        advance_amount_with_overall_payments_for_future = 0
        if self.overall_payments_for_future > 0:
            if (self.overall_payments_for_future - advance.initial_amount) > 0:
                self.overall_payments_for_future = self.overall_payments_for_future - advance.initial_amount
                self.overall_advance_balance = 0
            else:
                self.overall_advance_balance += (advance.initial_amount - self.overall_payments_for_future)
                advance_amount_with_overall_payments_for_future = advance.initial_amount - self.overall_payments_for_future
                self.overall_payments_for_future = 0
                
        else:
            self.overall_advance_balance += advance.initial_amount
            advance_amount_with_overall_payments_for_future = advance.initial_amount
        advance.current_amount = advance_amount_with_overall_payments_for_future
        self.advances.append(advance)

    def process_payment(self, payment: Tuple[int, str, int, str], event_datetime: datetime) -> None:
        """
        Process payment event following this logic:

        1)Reduce overall_interest_payable_balance
        2)Deduct all possible advances current amount
        3)If there's a remaning store it in self.overall_payments_for_future
        """
        payment_amount = payment[2]
        self.overall_interest_payable_balance = self.get_overall_interest(event_datetime)
            
        if payment_amount > self.overall_interest_payable_balance:
            # only pay overall_interest_payable_balance
            self.overall_interest_paid += self.overall_interest_payable_balance
        else:
            # event_amount is not enough to cover all overall_interest_payable_balance
            self.overall_interest_paid += payment_amount
        amount_after_interest_payed = Decimal(payment_amount) - self.overall_interest_payable_balance

        if amount_after_interest_payed > 0:
            self.reduce_advances(amount_after_interest_payed, event_datetime)
            amount_after_advance_balance_payed = Decimal(amount_after_interest_payed) - self.overall_advance_balance
            if amount_after_advance_balance_payed > 0:
                # all advances paid, save extra for future payments
                self.overall_advance_balance = 0
                self.overall_payments_for_future += amount_after_advance_balance_payed
            else:
                self.overall_advance_balance -= Decimal(amount_after_interest_payed)


    def process_event(self, event: Tuple[int, str, int, str], end_datetime: datetime) -> None:
        """
        Takes care of processing any type of event
        """
        event_datetime = datetime.strptime(event[3], "%Y-%m-%d")
        if event_datetime > end_datetime:
            return
        event_type = event[1]
        if event_type == self.ADVANCE_EVENT:
            advance_attrs =  list(event) + [0] + [event_datetime]
            self.process_advance(Advance(*advance_attrs))
        elif event_type == self.PAYMENT_EVENT:
            self.process_payment(event, event_datetime)
        else:
            return

    def get_advances_summary(
        self,
        events: Iterable[Tuple[int, str, int, str]],
        end_date: str) -> Tuple[Decimal, Decimal, Decimal, Decimal]:
        """
        In charge of processing the list of events and calculating the expected summary stats for advances

        Notes:
            1)If the event date being processed is not within the end_date range, event is not processed at all
            2)After processing all events we calculate get_overall_interest again to account for the days between
            the last event was processed and the end_date argument
        """
        end_datetime = datetime.strptime(end_date, "%Y-%m-%d")
        for event in events:
            self.process_event(event, end_datetime)

        # calculate extra interest generated from last event until end date inclusive
        self.overall_interest_payable_balance = self.get_overall_interest((end_datetime + timedelta(days=1)))
        return(
            self.overall_advance_balance,
            self.overall_interest_payable_balance,
            self.overall_interest_paid,
            self.overall_payments_for_future
        )
