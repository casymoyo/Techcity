from .models import Account

def calculate_expenses_totals(expense_queryset):
    """Calculates the total cost of all expenses in a queryset."""

    total_cost = 0
    for item in expense_queryset:
        total_cost += item.amount
    return total_cost


def account_identifier(request, currency, payment_method):
    """Identifies the account name and the account type to be debited or credited."""

    account_type = Account.AccountType[payment_method.upper()] 
    account_name = f"{request.user.branch} {currency.name} {payment_method.capitalize()} Account"

    return {
        'account_name':account_name,
        'account_type':account_type
    }
    
