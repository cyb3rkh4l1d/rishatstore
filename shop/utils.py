from functools import wraps
from stripe import StripeError
from rest_framework import status
from rest_framework.response import Response




#OrderValidation
class OrderValidationError(Exception):
    """This custom exception for OrderValidation"""
    pass

#this decorator function handles payment validation
def handle_payment_exceptions(view_func):
    @wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        try:
            return view_func(self, request, *args, **kwargs)
        except OrderValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except StripeError as e:
            return Response({'error': f'Stripe error: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f'Server error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return wrapper

