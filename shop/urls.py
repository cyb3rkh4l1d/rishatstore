from rest_framework_nested import routers
from django.urls import path, include
from .views import  ItemViewSet, BuyItemViewSet, OrderViewSet, StripePaymentView, CartViewSet, CartItemViewSet

app_name = "shop"

router = routers.DefaultRouter()

router.register('items', ItemViewSet, basename='items') #/api/items/
router.register('buy', BuyItemViewSet, basename='buy') #/api/buy/{id}
router.register('orders', OrderViewSet, basename='orders') #/api/orders, /api/orders/{id}
router.register('payment', StripePaymentView, basename='payment') #/api/payment/sessions/,/api/payment/cancel/,/api/payment/confirm/

#This carts api is not in the task, but i implement it to facilitaet Order operation, you may ignore them.
router.register('carts', CartViewSet, basename='carts') 
carts_router = routers.NestedDefaultRouter(router, 'carts', lookup='cart') 
carts_router.register('items', CartItemViewSet, basename='cart-items')


urlpatterns = router.urls + carts_router.urls
