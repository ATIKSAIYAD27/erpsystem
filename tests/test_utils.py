from app.utils import indian_currency, indian_number, indian_date

def test_indian_currency_basic():
    assert indian_currency(100000) == 'Rs. 1,00,000.00'

def test_indian_currency_zero():
    assert indian_currency(0) == 'Rs. 0.00'

def test_indian_currency_none():
    assert indian_currency(None) == 'Rs. 0.00'

def test_indian_currency_negative():
    assert indian_currency(-5000) == '-Rs. 5,000.00'

def test_indian_currency_small():
    assert indian_currency(999) == 'Rs. 999.00'

def test_indian_currency_decimal():
    assert indian_currency(1234.56) == 'Rs. 1,234.56'

def test_indian_number_basic():
    assert indian_number(100000) == '1,00,000.00'

def test_indian_number_zero():
    assert indian_number(0) == '0.00'

def test_indian_number_none():
    assert indian_number(None) == '0'

def test_indian_date_valid():
    from datetime import date
    assert indian_date(date(2024, 1, 15)) == '15/01/2024'

def test_indian_date_string():
    assert indian_date('2024-01-15') == '15/01/2024'

def test_indian_date_none():
    assert indian_date(None) == ''

def test_indian_date_invalid():
    assert indian_date('not-a-date') == 'not-a-date'