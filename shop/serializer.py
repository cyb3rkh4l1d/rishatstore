from decimal import Decimal
from rest_framework import serializers
from django.db import transaction
from django.conf import settings
from .models import Cart, CartItem, Item, OrderItem, Order,Discount,Tax


#Item Serializer
class ItemSerializer(serializers.ModelSerializer):

    class Meta:
        model = Item
        fields = ['id', 'name', 'description', 'price', 'currency']

#OrderItem Serializer
class OrderItemSerializer(serializers.ModelSerializer):
    """
        this serilizer display OrderItem
    """
    item = ItemSerializer(read_only=True)
    
    class Meta:
        model = OrderItem
        fields = ['id', 'item', 'quantity', 'unit_price']

#Order Serializer
class OrderSerializer(serializers.ModelSerializer):
    """
        this serilizer display Order details.
    """
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'created_at', 'payment_status', 'stripe_payment_intent_id',
            'items', 'subtotal', 'discount_amount', 'tax_amount', 'total', 'order_currency'
        ]
        read_only_fields = ['id', 'created_at', 'payment_status', 'subtotal', 'discount_amount', 'tax_amount', 'total']

#CreateOrderSerializer 
class CreateOrderSerializer(serializers.Serializer):
    """
    When order is created.
        -> Order request must have cart_id
        -> This serializer , will use cart_id , to get list of orderitems in the cart
        -> total, subtotal, discount_amount and tax_amount is calculated here.
        -> because multiple database update happen here, i use transaction.Atomic, 
            -> To ensure changes is rolled back if there is an error in one of the database operation
    """
    cart_id = serializers.UUIDField()
    currency = serializers.ChoiceField(choices=[(settings.BASE_CURRENCY, settings.BASE_CURRENCY), (settings.EUR_CURRENCY, settings.EUR_CURRENCY)], default=settings.BASE_CURRENCY)

    def validate_cart_id(self, cart_id):
        if not Cart.objects.filter(pk=cart_id).exists():
            raise serializers.ValidationError('No cart with the given ID was found.')
        if CartItem.objects.filter(cart_id=cart_id).count() == 0:
            raise serializers.ValidationError('Cart is empty.')
        return cart_id

    def save(self, **kwargs):
        with transaction.atomic():
            cart_id = self.validated_data['cart_id']
            target_currency = self.validated_data['currency']
            
            # Create order with selected currency
            order = Order.objects.create(order_currency=target_currency)
            
            cart_items = CartItem.objects.select_related('item').filter(cart_id=cart_id)
            
            order_items = []
            for cart_item in cart_items:
                item = cart_item.item
                unit_price = item.price
                
                # Convert price if currency is different
                if target_currency == settings.EUR_CURRENCY:
                    unit_price = item.price * Decimal.from_float(settings.CURRENCY_RATE)
                
                order_items.append(OrderItem(
                    order=order,
                    item=item,
                    unit_price=unit_price,
                    quantity=cart_item.quantity,
                ))
            
            OrderItem.objects.bulk_create(order_items)
            
            # Calculate and save subtotal totals
            subtotal = sum(item.quantity * item.unit_price for item in order.items.all())
            
            # Calculate discount
            active_discount = Discount.objects.filter(is_active=True).first()
            discount_amount = subtotal * (active_discount.percentage / Decimal(100)) if active_discount else Decimal(0)
        
            
            # Calculate  Tax
            subtotal_after_discount = subtotal - discount_amount
            active_tax = Tax.objects.filter(is_active=True).first()
            tax_amount = subtotal_after_discount * (active_tax.percentage / Decimal(100)) if active_tax else Decimal(0)
            
            #calculate total after tax and discount applied
            total = subtotal_after_discount + tax_amount
            
            # Save to ordermodel
            order.subtotal = subtotal
            order.discount_amount = discount_amount
            order.tax_amount = tax_amount
            order.total = total
            order.save()
            
            # Clear the cart
            Cart.objects.filter(pk=cart_id).delete()
            
            return order


#This serializer validates order_id during stripe payment. Its used by StripePaymentViewSet
class OrderIdSerializer(serializers.Serializer):
    order_id = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(),
        error_messages={'error': 'Order not found'}
    )

#BuyItemSerializer
class BuyItemSerializer(serializers.Serializer):
    """
    This Serializer is for direct item purchases with currency conversion
    -> GET /api/buy/{item_id}?cur={USD|EUR}
    -> It must have item id
    -> currency field if not available will be default to USD.
    -> it process payment of a single item only.
    -> because multiple database operation happen, i use transaction.Atomic to ensure operation is rolled back.
    -> it works like this:
        -> it will use item_id to get the info about the item
        -> if cur is EUR , it convert item price to EUR
        -> it then create an Order for this single item
        -> Then use the OrderId to initiated a payment using stripe.
        Note: This Serializer supposed to be with CreateOrderSerializer, but because the task requires implementing single payment by itemid, that's why i separated it from CreatOrderSerialzier for demonstration.
    """
    
    def validate(self, attrs):
        # Get item_id from URL
        item_id = self.context['view'].kwargs.get('pk')
        
        if not item_id:
            raise serializers.ValidationError('Item ID is required')
        
        try:
            item = Item.objects.get(id=item_id)
            attrs['item'] = item
            
            # Get currency from request query parameters
            request = self.context.get('request')
            target_currency = request.GET.get('cur', 'USD').upper() #if no, default to USD
            attrs['target_currency'] = target_currency
            
        except Item.DoesNotExist:
            raise serializers.ValidationError('Item not found')
        
        return attrs

    def create(self, validated_data):
        item = validated_data['item']
        target_currency = validated_data['target_currency']
        
        with transaction.atomic():
            # Create order with selected currency
            order = Order.objects.create(order_currency=target_currency)
            
            # Calculate unit price with currency conversion
            unit_price = item.price
          
            if target_currency == settings.EUR_CURRENCY:
                print("Yes: UE")
                unit_price = item.price * Decimal.from_float(settings.CURRENCY_RATE)
            
            # Create single order item with converted price
            order_item = OrderItem(
                order=order,
                item=item,
                unit_price=unit_price,
                quantity=1
            )
            order_item.save()
            
            # CALCULATE AND SAVE TOTALS (same as CreateOrderSerializer)
            subtotal = sum(item.quantity * item.unit_price for item in order.items.all())
            
            active_discount = Discount.objects.filter(is_active=True).first()
            discount_amount = subtotal * (active_discount.percentage / Decimal(100)) if active_discount else Decimal(0)
            
            subtotal_after_discount = subtotal - discount_amount
            active_tax = Tax.objects.filter(is_active=True).first()
            tax_amount = subtotal_after_discount * (active_tax.percentage / Decimal(100)) if active_tax else Decimal(0)
            
            total = subtotal_after_discount + tax_amount
            
            # Save calculated totals to model
            order.subtotal = subtotal
            order.discount_amount = discount_amount
            order.tax_amount = tax_amount
            order.total = total
            order.save()
            
            return order



"""
This Serializer Are Out Of Scope Of This Task.
but because the task needs to combine multiple order of items and make a single stripe payment.
thats why i created a Cart Serializer to facilitate this.
You may ignore this section
"""

class CartItemSerializer(serializers.ModelSerializer):
    item = ItemSerializer(read_only=True)
    total_price = serializers.SerializerMethodField()

    def get_total_price(self, cart_item: CartItem):
        return cart_item.quantity * cart_item.item.price

    class Meta:
        model = CartItem
        fields = ['id', 'item', 'quantity', 'total_price']

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()

    def get_total_price(self, cart: Cart):
        return sum([item.quantity * item.item.price for item in cart.items.all()])

    class Meta:
        model = Cart
        fields = ['id', 'created_at', 'items', 'total_price']

class AddCartItemSerializer(serializers.ModelSerializer):
    item_id = serializers.IntegerField()

    def validate_item_id(self, value):
        if not Item.objects.filter(pk=value).exists():
            raise serializers.ValidationError('No item with the given ID was found.')
        return value

    def save(self, **kwargs):
        cart_id = self.context['cart_id']
        item_id = self.validated_data['item_id']
        quantity = self.validated_data['quantity']

        try:
            cart_item = CartItem.objects.get(cart_id=cart_id, item_id=item_id)
            cart_item.quantity += quantity
            cart_item.save()
            self.instance = cart_item
        except CartItem.DoesNotExist:
            self.instance = CartItem.objects.create(cart_id=cart_id, **self.validated_data)

        return self.instance

    class Meta:
        model = CartItem
        fields = ['id', 'item_id', 'quantity']

class UpdateCartItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = CartItem
        fields = ['quantity']
