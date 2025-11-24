import pytest
from rest_framework import status

@pytest.mark.django_db
class TestOrders:
    def test_create_order_from_cart_returns_201(self, api_client, create_cart_item):
        cart_item = create_cart_item(quantity=2)
        
        response = api_client.post(
            '/api/orders/',
            {'cart_id': str(cart_item.cart.id), 'currency': 'USD'}
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['total'] > 0
        assert response.data['order_currency'] == 'USD'

    def test_get_existing_order_by_orderId_returns_200(self, api_client, create_order):
        order = create_order()
        
        response = api_client.get(f'/api/orders/{order.id}/')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == str(order.id)

    def test_get_nonexisting_order_by_orderId_returns_200(self, api_client, create_order):
        
        response = api_client.get(f'/api/orders/1xhau/')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

