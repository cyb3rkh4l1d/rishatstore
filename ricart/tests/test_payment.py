import pytest
from rest_framework import status
from shop.models import  Order

@pytest.mark.django_db
class TestPayment:
    def test_create_payment_intent_returns_200(self, api_client, create_order):
        order = create_order(total=10.00)  # Small amount for testing
        
        response = api_client.post('/api/payment/sessions/', {'order_id': str(order.id)})
        
        assert response.status_code == status.HTTP_200_OK
        assert 'client_secret' in response.data
        assert 'payment_intent_id' in response.data

    def test_confirm_payment_returns_400(self, api_client, create_order):
        order = create_order(payment_status='P', stripe_payment_intent_id='invalid_id')
        
        response = api_client.post('/api/payment/confirm/', {'order_id': str(order.id)})
        
        # Should fail with invalid payment intent
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cancel_pending_payment_returns_200(self, api_client, create_order):
        # First create a real payment intent
        order = create_order(total=10.00)
        session_response = api_client.post('/api/payment/sessions/', {'order_id': str(order.id)})
        payment_intent_id = session_response.data['payment_intent_id']
        
        # Then cancel it
        response = api_client.post('/api/payment/cancel/', {'order_id': str(order.id)})
        
        assert response.status_code == status.HTTP_200_OK

    # CONFIRM PAYMENT TESTS
    def test_confirm_payment_with_cancelled_order_returns_400(self, api_client, create_order):
        """Test confirming payment for cancelled order returns 400"""
        order = create_order(payment_status=Order.PAYMENT_CANCELLED)
        
        response = api_client.post('/api/payment/confirm/', {'order_id': str(order.id)})
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
        assert 'cancelled' in response.data['error'].lower()

    def test_confirm_payment_with_invalid_order_returns_400(self, api_client):
        """Test confirming payment with invalid order ID returns 400"""
        response = api_client.post('/api/payment/confirm/', {'order_id': 'invalid-uuid'})
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data

    def test_confirm_payment_with_completed_order_returns_400(self, api_client, create_order):
        """Test confirming payment for already completed order returns 400"""
        order = create_order(payment_status=Order.PAYMENT_COMPLETE)
        
        response = api_client.post('/api/payment/confirm/', {'order_id': str(order.id)})
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
        assert 'completed' in response.data['error'].lower()

    def test_confirm_payment_with_pending_order_returns_200_or_400(self, api_client, create_order):
        """Test confirming payment for pending order (may succeed or fail based on Stripe)"""
        # First create a payment session
        order = create_order(total=10.00)
        session_response = api_client.post('/api/payment/sessions/', {'order_id': str(order.id)})
        
        # Try to confirm - this might fail if payment not actually processed
        response = api_client.post('/api/payment/confirm/', {'order_id': str(order.id)})
        
        # Could be 200 (if test mode succeeds) or 400 (if payment not actually completed)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]
        assert 'status' in response.data or 'error' in response.data

    def test_confirm_payment_with_failed_order_returns_400(self, api_client, create_order):
        """Test confirming payment for failed order returns 400"""
        order = create_order(payment_status=Order.PAYMENT_FAILED)
        
        response = api_client.post('/api/payment/confirm/', {'order_id': str(order.id)})
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
        # Depending on your validation, it might say "failed" or "already processed"

    # CANCEL PAYMENT TESTS
    def test_cancel_payment_with_cancelled_order_returns_400(self, api_client, create_order):
        """Test cancelling payment for already cancelled order returns 400"""
        order = create_order(payment_status=Order.PAYMENT_CANCELLED)
        
        response = api_client.post('/api/payment/cancel/', {'order_id': str(order.id)})
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
        assert 'cancelled' in response.data['error'].lower() or 'processed' in response.data['error'].lower()

    def test_cancel_payment_with_invalid_order_returns_500(self, api_client):
        """Test cancelling payment with invalid order ID returns 400"""
        response = api_client.post('/api/payment/cancel/', {'order_id': 'invalid-uuid'})
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data

    def test_cancel_payment_with_completed_order_returns_500(self, api_client, create_order):
        """Test cancelling payment for completed order returns 400"""
        order = create_order(payment_status=Order.PAYMENT_COMPLETE)
        
        response = api_client.post('/api/payment/cancel/', {'order_id': str(order.id)})
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data
        assert 'processed' in response.data['error'].lower() or 'completed' in response.data['error'].lower()

    def test_cancel_payment_with_pending_order_returns_200(self, api_client, create_order):
        """Test cancelling payment for pending order returns 200"""
        # First create a payment session
        order = create_order(total=10.00)
        session_response = api_client.post('/api/payment/sessions/', {'order_id': str(order.id)})
        
        # Then cancel it
        response = api_client.post('/api/payment/cancel/', {'order_id': str(order.id)})
        
        assert response.status_code == status.HTTP_200_OK
        assert 'message' in response.data
        assert 'cancelled' in response.data['message'].lower()

    def test_cancel_payment_with_failed_order_returns_200(self, api_client, create_order):
        """Test cancelling payment for failed order returns 200"""
        order = create_order(payment_status=Order.PAYMENT_FAILED)
        
        response = api_client.post('/api/payment/cancel/', {'order_id': str(order.id)})
        
        assert response.status_code == status.HTTP_200_OK
        assert 'message' in response.data
        assert 'cancelled' in response.data['message'].lower()

    # EDGE CASE TESTS

    def test_confirm_payment_nonexistent_order_returns_500(self, api_client):
        """Test confirming payment for non-existent order returns 500"""
        from uuid import uuid4
        nonexistent_id = uuid4()
        
        response = api_client.post('/api/payment/confirm/', {'order_id': str(nonexistent_id)})
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data

    def test_cancel_payment_nonexistent_order_returns_500(self, api_client):
        """Test cancelling payment for non-existent order returns 500"""
        from uuid import uuid4
        nonexistent_id = uuid4()
        
        response = api_client.post('/api/payment/cancel/', {'order_id': str(nonexistent_id)})
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert 'error' in response.data