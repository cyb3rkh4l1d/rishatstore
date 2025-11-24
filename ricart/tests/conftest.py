import pytest
from model_bakery import baker
from shop.models import Item, Cart, CartItem, Order, Discount, Tax
from rest_framework.test import APIClient

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def create_item():
    def _create_item(**kwargs):
        return baker.make(Item, **kwargs)
    return _create_item

@pytest.fixture
def create_cart():
    def _create_cart():
        return Cart.objects.create()
    return _create_cart

@pytest.fixture
def create_cart_item(create_cart, create_item):
    def _create_cart_item(cart=None, item=None, quantity=1):
        if not cart:
            cart = create_cart()
        if not item:
            item = create_item()
        return CartItem.objects.create(cart=cart, item=item, quantity=quantity)
    return _create_cart_item

@pytest.fixture
def create_order(create_item):
    def _create_order(**kwargs):
        order = baker.make(Order, **kwargs)
        item = create_item()
        baker.make('shop.OrderItem', order=order, item=item, quantity=1, unit_price=item.price)
        return order
    return _create_order

@pytest.fixture
def create_discount():
    def _create_discount(**kwargs):
        return baker.make(Discount, **kwargs)
    return _create_discount

@pytest.fixture
def create_tax():
    def _create_tax(**kwargs):
        return baker.make(Tax, **kwargs)
    return _create_tax