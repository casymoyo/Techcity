from django.contrib.sessions.middleware import SessionMiddleware

def get_cart_session(request):
  """
  Retrieves the cart items from the session or creates a new one.
  """
  session = request.session
  session_key = 'transfer_cart'
  cart = session.get(session_key, {})
  if not cart:
    cart = {}
    session[session_key] = cart
  return cart

class TransferCartItem:
  """
  Represents a product in the transfer cart.
  """
  def __init__(self, product_id, branch_from, branch_to, price, quantity):
    self.product_id = product_id
    self.branch_from = branch_from
    self.branch_to = branch_to
    self.price = price
    self.quantity = quantity

  def get_total(self):
    """
    Calculates the total price for this item (quantity * price).
    """
    return self.price * self.quantity

def add_to_cart(request, product_id, branch_from, branch_to, price, quantity):
  """
  Adds a product to the cart with specified details.
  """
  cart = get_cart_session(request)
  cart_item = cart.get(str(product_id))
  if cart_item:
    # Update quantity if product already exists in cart
    cart_item.quantity += quantity
  else:
    # Create a new TransferCartItem instance
    cart_item = TransferCartItem(product_id, branch_from, branch_to, price, quantity)
  cart[str(product_id)] = cart_item
  request.session.save()

def remove_from_cart(request, product_id):
  """
  Removes a product from the cart.
  """
  cart = get_cart_session(request)
  if str(product_id) in cart:
    del cart[str(product_id)]
  request.session.save()

def get_cart_items(request):
  """
  Returns all the items present in the cart as TransferCartItem objects.
  """
  cart = get_cart_session(request)
  cart_items = []
  for product_id, item_details in cart.items():
    cart_items.append(TransferCartItem(
        product_id=int(product_id),
        branch_from=item_details['branch_from'],
        branch_to=item_details['branch_to'],
        price=item_details['price'],
        quantity=item_details['quantity'],
    ))
  return cart_items

def get_cart_total(request):
  """
  Calculates the total price of all items in the cart.
  """
  cart_items = get_cart_items(request)
  total = sum(item.get_total() for item in cart_items)
  return total

def clear_cart(request):
  """
  Clears all items from the cart.
  """
  cart = get_cart_session(request)
  cart.clear()
  request.session.save()
