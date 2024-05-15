from . models import Inventory
from django.db import models

def calculate_inventory_totals(inventory_queryset):
    """Calculates the total cost and total potential selling price of inventory items.

    Args:
        inventory_queryset: A QuerySet of Inventory objects.

    Returns:
        A tuple containing:
            - total_cost: The total cost of acquiring the inventory items.
            - total_price: The total potential selling price of the inventory items.
    """

    total_cost = 0
    total_price = 0

    for item in inventory_queryset:
        item_total_cost = item.quantity * item.cost
        total_cost += item_total_cost
        
        if hasattr(item, 'price'):  
            item_total_price = item.quantity * item.price
            total_price += item_total_price
        else:
            print(f"Warning: Item {item} does not have a 'price' attribute.")
    print(total_price)
    return total_cost, total_price



