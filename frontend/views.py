from django.views.generic import TemplateView
from django.conf import settings

class HomeView(TemplateView):
    """Render home.html using class-based view"""
    template_name = 'home.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['STRIPE_PUBLIC_KEY'] = settings.STRIPE_PUBLISHABLE_KEY
        context['STRIPE_PUBLIC_KEY_EUR'] = settings.STRIPE_PUBLISHABLE_KEY_EUR
        return context