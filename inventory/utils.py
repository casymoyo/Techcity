from . models import Inventory
from django.db import models
from loguru import logger

def calculate_inventory_totals(inventory_queryset):
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
    return total_cost, total_price

def average_inventory_cost(product_id, new_cost, new_units):
    """ method for calculating Weighted Average Cost Price (WAC)"""
    average_cost = 0
    try:
        product = Inventory.objects.get(id=product_id)
    except Exception as e:
        logger.info(f'{e}')

    old_units = product.quantity
    old_cost = product.cost 

    logger.info(f'old: {old_units}, {old_cost}, new: {new_cost}, {new_units}')

    average_cost = ((old_cost * old_units) + (new_cost * new_units)) / (new_units + old_units)
    logger.info(f'Average stock: {average_cost}')
    return average_cost





