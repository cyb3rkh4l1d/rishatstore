import pytest
from rest_framework import status

@pytest.mark.django_db
class TestBuy:
    def test_buy_item_default_usd_currency_returns_201(self, api_client, create_item):
        item = create_item(price=100.00)
        
        response = api_client.get(f'/api/buy/{item.id}/')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['order_currency'] == 'USD'

    def test_buy_item_with_eur_currency_returns_201(self, api_client, create_item):
        item = create_item(price=100.00)
        
        response = api_client.get(f'/api/buy/{item.id}/?cur=EUR')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['order_currency'] == 'EUR'