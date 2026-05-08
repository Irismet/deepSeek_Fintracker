from scipy.optimize import brentq
from datetime import datetime
import numpy as np

def xnpv(rate, cashflows):
    """Calculate NPV with irregular intervals"""
    if rate <= -1.0:
        return float('inf')
    
    total = 0.0
    for date, amount in cashflows:
        if isinstance(date, datetime):
            date = date.timestamp()
        # Используем первый cashflow как базовую дату
        if cashflows[0][0] == date:
            total += amount
        else:
            years = (date - cashflows[0][0]) / 31536000.0  # секунд в году
            total += amount / ((1 + rate) ** years)
    return total

def calculate_xirr(cashflows, guess=0.1):
    """
    Calculate XIRR
    cashflows: list of (date, amount)
    """
    if len(cashflows) < 2:
        return None
    
    try:
        # Убеждаемся, что первый cashflow - отток (инвестиция)
        # Сортируем по дате
        cashflows.sort(key=lambda x: x[0])
        
        # Используем brentq для поиска корня
        def f(rate):
            return xnpv(rate, cashflows)
        
        # Ищем корень между -0.99 и 10.0
        result = brentq(f, -0.99, 10.0, maxiter=1000)
        return result * 100  # в процентах
    except (ValueError, RuntimeError):
        return None