import stripe
from stripe import StripeError
from functools import wraps
from rest_framework import status,viewsets
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, GenericViewSet
from rest_framework.mixins import CreateModelMixin, RetrieveModelMixin, DestroyModelMixin
from rest_framework.decorators import action
from rest_framework.viewsets import ReadOnlyModelViewSet
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from .models import Item, Cart, CartItem, Order
from .serializer import ItemSerializer, BuyItemSerializer,CartSerializer, CartItemSerializer, AddCartItemSerializer, UpdateCartItemSerializer, CreateOrderSerializer,  OrderSerializer, OrderIdSerializer
from .utils import handle_payment_exceptions, OrderValidationError

#ItemView
class ItemViewSet(ReadOnlyModelViewSet):
    """
        -> GET /api/items
        -> Only Read(GET) operation is allowed
        -> it returns list of items.
    """
    queryset = Item.objects.all()
    serializer_class = ItemSerializer

#BuyItemView
class BuyItemViewSet(RetrieveModelMixin, GenericViewSet):
    """
        -> GET /api/buy/{id}?cur={USD|EUR}
        -> Only Read(GET) operation is allowed
        -> it create order for a single item. 
            -> the orderid will be used to create a payment to stripe.
         Note: This Viewset supposed to be with OrderViewSet, but because the task requires implementing single payment by itemid, that's why i separated it from OrderViewSet for demonstration.

    """
    serializer_class = BuyItemSerializer

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(data={})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

#OrderView
class OrderViewSet(CreateModelMixin, RetrieveModelMixin, GenericViewSet):
    """
        -> GET /api/orders/{id} : get detail about specific order by it id.
        -> POST /api/orders/ : this will take cart_id and create order.
    """
    queryset = Order.objects.prefetch_related('items__item').all()
    
    def get_serializer_class(self):
        if self.request.method == 'POST': #create order if its POST
            return CreateOrderSerializer
        return OrderSerializer

    #create an order by cart_id
    def create(self, request, *args, **kwargs):
        """POST /api/orders/ {cart_id : {cart_id}, currency: {USD|EUR}}"""
        serializer = CreateOrderSerializer(
            data=request.data, 
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


#StripePaymentViewSet



class StripePaymentView(viewsets.ViewSet):
    """
            -> POST /api/checkout/sessions/ {order_id: {order_id}}
        -> POST /api/checkout/cancel/ {order_id: {order_id}}
        -> POST /api/checkout/confirm/ {order_id: {order_id}}
        -> This view handles all the payment flow
        -> it takes order_id, get or create payment_intent_id from order, use it to perform payment operation.
    """
    def _get_order(self, request):
        """
        validate orderId
        """
        serializer = OrderIdSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data['order_id']

    def _set_stripe_currency(self, currency):
        """Set Stripe API key based on currency"""
        if currency == 'EUR':
            stripe.api_key = settings.STRIPE_SECRET_KEY_EUR
        else:
            stripe.api_key = settings.STRIPE_SECRET_KEY

    def _validate_order_for_payment(self, order):
        """Validate order can process payment, raise exception if not"""
        if order.payment_status == Order.PAYMENT_CANCELLED:
            raise OrderValidationError('Order is cancelled')
        if order.payment_status == Order.PAYMENT_COMPLETE:
            raise OrderValidationError('Order already completed')

    def _validate_order_for_cancellation(self, order):
        """Validate order can be cancelled, raise exception if not"""
        if order.payment_status not in [Order.PAYMENT_PENDING, Order.PAYMENT_FAILED]:
            raise OrderValidationError('Cannot cancel processed order')

    @action(detail=False, methods=['post'])
    @handle_payment_exceptions
    def sessions(self, request):
        """
            POST /api/checkout/sessions/ - 
            -> Create payment intent for order
            -> it get amount and currency from order, 
            -> then generates payment_intent_id for the order
            -> then saves payment_intent_id to the order, and return response.
              
        """
        order = self._get_order(request)
        self._set_stripe_currency(order.order_currency)
        
        # Validate and raise exception if invalid
        self._validate_order_for_payment(order)

        intent = stripe.PaymentIntent.create(
            amount=int(order.total * 100),
            currency=order.order_currency.lower(),
            metadata={'order_id': str(order.id)},
            automatic_payment_methods={'enabled': True},
        )
        
        order.stripe_payment_intent_id = intent['id']
        order.save()
        
        return Response({
            'client_secret': intent['client_secret'],
            'payment_intent_id': intent['id'],
            'amount': order.total,
            'currency': order.order_currency
        },status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    @handle_payment_exceptions
    def cancel(self, request):
        """
             POST /api/checkout/cancel/ - 
            -> Cancel payment for specific order by order_id.
            -> it uses order_id to get payment_intent_id from the order.
            -> then check requirements and then cancel the order.
            -> then update the payment status for the order to PAYMENT_CANCELLED.
              
        """
        order = self._get_order(request)
        self._set_stripe_currency(order.order_currency)
        
        # Validate and raise exception if invalid
        self._validate_order_for_cancellation(order)
        
        if order.stripe_payment_intent_id and order.payment_status == Order.PAYMENT_PENDING:
            stripe.PaymentIntent.cancel(order.stripe_payment_intent_id)
        
        order.payment_status = Order.PAYMENT_CANCELLED
        order.save()
        
        return Response({'message': 'Payment cancelled successfully'},status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    @handle_payment_exceptions
    def confirm(self, request):
        """
             POST /api/checkout/confirm/ - 
            -> Confirm payment for specific order by order_id.
            -> it uses order_id to get payment_intent_id from the order.
            -> then check requirements and then confirm the order.
            -> then update the payment status for the order to either PAYMENT_COMPLETE or PAYMENT_Failed.
            TODO: Best practice is to use webhook to handle payment.
        
        """
        order = self._get_order(request)
        self._set_stripe_currency(order.order_currency)
        
        # Validate and raise exception if invalid
        self._validate_order_for_payment(order)

        intent = stripe.PaymentIntent.retrieve(order.stripe_payment_intent_id)
        
        order.payment_status = Order.PAYMENT_COMPLETE if intent.status == 'succeeded' else Order.PAYMENT_FAILED
        order.save()
        
        result = {
            'status': 'success' if intent.status == 'succeeded' else 'failed',
            'message': 'Payment confirmed successfully' if intent.status == 'succeeded' else f'Payment failed: {intent.status}',
            'order_id': str(order.id)
        }
        
        return Response(result, status=status.HTTP_200_OK if result['status'] == 'success' else status.HTTP_400_BAD_REQUEST)

"""
This View Are Out Of Scope Of This Task.
but because the task needs to combine multiple order of items and make a single stripe payment.
thats why i created a Cart View to facilitate this.
You may ignore this section
"""
class CartViewSet(CreateModelMixin, RetrieveModelMixin, DestroyModelMixin, GenericViewSet):
    queryset = Cart.objects.prefetch_related('items__item').all()
    serializer_class = CartSerializer

    def create(self, request, *args, **kwargs):
        cart = Cart.objects.create()
        serializer = self.get_serializer(cart)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class CartItemViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AddCartItemSerializer
        elif self.request.method == 'PATCH':
            return UpdateCartItemSerializer
        return CartItemSerializer

    def get_serializer_context(self):
        return {'cart_id': self.kwargs['cart_pk']}

    def get_queryset(self):
        return CartItem.objects.filter(cart_id=self.kwargs['cart_pk']).select_related('item')
