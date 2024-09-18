def calculate_expenses_totals(expense_queryset):
    """Calculates the total cost of all expenses in a queryset."""

    total_cost = 0
    for item in expense_queryset:
        total_cost += item.amount
    return total_cost



