"""Run with:  python test_splitter.py   (prints OK if the maths is right)"""
from splitter import parse_people, split_bill, to_cents


def check_even_split():
    items = [(to_cents(10.00), ["A", "B", "C"])]
    totals, unassigned = split_bill(items, ["A", "B", "C"], to_cents(1.00))
    assert sum(totals.values()) == 1100 and unassigned == 0
    assert sorted(totals.values()) == [366, 366, 368]


def check_item_split_with_tax_and_tip():
    items = [(to_cents(20.00), ["A"]), (to_cents(10.00), ["B"]), (to_cents(6.00), ["A", "B"])]
    totals, _ = split_bill(items, ["A", "B"], to_cents(3.60))
    assert sum(totals.values()) == 3960          # 36.00 + 3.60
    assert totals["A"] > totals["B"]


def check_unassigned_and_names():
    totals, unassigned = split_bill([(500, [])], ["A", "B"], 0)
    assert unassigned == 500 and sum(totals.values()) == 0
    assert parse_people("Asha, Ravi , asha,,") == ["Asha", "Ravi"]


def check_discount_and_no_subtotal():
    totals, _ = split_bill([(-100, ["A", "B"])], ["A", "B"], 10)
    assert sum(totals.values()) == -90


if __name__ == "__main__":
    check_even_split()
    check_item_split_with_tax_and_tip()
    check_unassigned_and_names()
    check_discount_and_no_subtotal()
    print("OK - all split tests passed")