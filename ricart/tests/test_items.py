import pytest
from rest_framework import status

@pytest.mark.django_db
class TestItems:
    """
        Test cases:
            -> 
    """
    def test_list_items_returns_200(self, api_client, create_item):
        create_item()
        create_item()
        
        response = api_client.get('/api/items/')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_get_existing_item_returns_200(self, api_client, create_item):
        """Test retrieving an existing item returns 200"""
        item = create_item()
        
        print(item.id)
        response = api_client.get(f'/api/items/{item.id}/')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == item.id
        assert response.data['name'] == item.name

    def test_get_nonexistent_item_returns_400(self, api_client):
        """Test retrieving non-existent item returns 400"""
        response = api_client.get('/api/items/10191983813813133131/')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert 'error' in response.data or 'detail' in response.data

    def test_get_item_with_non_integer_id_returns_404(self, api_client):
        """Test non-integer ID returns 404"""
        invalid_ids = ['abc', '123abc', 'null', 'undefined']
        
        for invalid_id in invalid_ids:
            response = api_client.get(f'/api/items/{invalid_id}/')
            assert response.status_code == status.HTTP_404_NOT_FOUND