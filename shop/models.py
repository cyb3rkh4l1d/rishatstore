import uuid
from decimal import Decimal
from django.db import models
from django.conf import settings

#Item Model

class Item(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2) 
    currency = models.CharField(max_length=3, choices=[(settings.BASE_CURRENCY, settings.BASE_CURRENCY), (settings.EUR_CURRENCY, settings.EUR_CURRENCY)], default=settings.BASE_CURRENCY)

    def __str__(self):
        return self.name  # This ensures items show by name
#Order Model
class Order(models.Model):
    """

 
    """
    #Payment Status
    PAYMENT_PENDING = 'P'
    PAYMENT_COMPLETE = 'C'
    PAYMENT_FAILED = 'F'
    PAYMENT_CANCELLED = 'X'  # Add cancelled status

    #Payment Status used in payment_status as choices.
    PAYMENT_STATUS = [
        (PAYMENT_PENDING, 'Pending'),
        (PAYMENT_COMPLETE, 'Complete'),
        (PAYMENT_FAILED, 'Failed'),
        (PAYMENT_CANCELLED, 'Cancelled'),  # Add this
    ]
    
    #Main attributes of Order model,
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    payment_status = models.CharField(max_length=1, choices=PAYMENT_STATUS, default=PAYMENT_PENDING)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True) 

    # Additional attributes of Order Model.
    order_currency = models.CharField(max_length=3, default=settings.BASE_CURRENCY) #selected currency for payment of this order
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)#total sum before discount and tax
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0) #discount amount for the order based on Discount Model
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0) #tax amount for the order based on Tax Model
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0) #total sum after discount and tex

#OrderItem Model
class OrderItem(models.Model):
    """
    Relationship:
    Order 1 -> * OrderItem : One to many 
    Item 1 -> * OrderItem : One To Many

    """
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='items') #Order cannot be deleted if it has order items..
    item = models.ForeignKey(Item, on_delete=models.PROTECT) #Item cannot be deleted if it has orders.
    quantity = models.PositiveSmallIntegerField() #Prevent Negative And Decimal Value
    unit_price = models.DecimalField(max_digits=10, decimal_places=2) #Prevent Negative Value



# Discount Model
class Discount(models.Model):
    """
    No relationship between Order Model And Discount Model To prevent Circular Dependency
    """
    name = models.CharField(max_length=100)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    is_active = models.BooleanField(default=False)  # Only one active discount
  
    # Only one discount should be enabled at a time.
    def save(self, *args, **kwargs):
        if self.is_active:
            Discount.objects.filter(is_active=True).update(is_active=False) #disable other discounts
        super().save(*args, **kwargs)

#Tax Model
class Tax(models.Model):
    """
    No relationship between Order Model And Tax Model To prevent Circular Dependency
    """
    name = models.CharField(max_length=100)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    is_active = models.BooleanField(default=False)  # Only one active tax
  
    # Only one Tax should be enabled at a time.
    def save(self, *args, **kwargs):
        if self.is_active:
            Tax.objects.filter(is_active=True).update(is_active=False) #disable other Taxes
        super().save(*args, **kwargs)


"""
This Model Are Out Of Scope Of This Task.
but because the task needs to combine multiple order of items and make a single stripe payment.
thats why i created a Cart Model to facilitate this.
"""
#Cart Model

class Cart(models.Model):


    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False) #UUID to prevent cart id from being guessed by any other.
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    @property
    def total_price(self):
        return sum(item.quantity * item.item.price for item in self.items.all()) #total price of all items in the cart

class CartItem(models.Model):
    """
    Relationship
    Cart 1 -> * CartItem : One To Many
    Item 1 -> * CartItem : One To Many
    """
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items') #Deleetin Cart Will delete the cartitem.
    item = models.ForeignKey(Item, on_delete=models.CASCADE) #Deleting Item will delete the CartItem
    quantity = models.PositiveIntegerField(default=1) #prevent Negative Or Decimal Number
    @property
    def total_price(self):
        return self.quantity * self.item.price #total price of the quantity of items.

