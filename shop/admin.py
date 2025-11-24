from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Sum
from django.utils import timezone
from .models import Item, Order, OrderItem, Discount, Tax

# Admin site customization
admin.site.site_header = "РишатStore Admin"
admin.site.site_title = "РишатStore Admin"
admin.site.index_title = "РишатStore Admin"

class ItemAdmin(admin.ModelAdmin):
    list_display = [
        'name', 
        'price', 
        'currency', 
        'order_count'
    ]
    list_filter = ['currency']
    search_fields = ['name', 'description']
    readonly_fields = ['currency']  # Only currency is readonly
    list_editable = ['price']
    list_per_page = 25
    
    # Fields shown when editing an existing item
    fieldsets = [
        (None, {
            'fields': ['name', 'description', 'price']
        }),
        ('Read-only Information', {
            'fields': ['currency'],
            'classes': ['collapse']
        }),
    ]
    
    # Fields shown when adding a new item (same as above but without currency)
    add_fieldsets = [
        (None, {
            'fields': ['name', 'description', 'price']
        }),
    ]
    
    def get_fieldsets(self, request, obj=None):
        if not obj:
            # When creating new item, use add_fieldsets (without currency)
            return self.add_fieldsets
        return super().get_fieldsets(request, obj)
    
    def get_readonly_fields(self, request, obj=None):
        if obj:
            # When editing existing item, currency is readonly
            return self.readonly_fields
        else:
            # When creating new item, no readonly fields
            return []
    
    def save_model(self, request, obj, form, change):
        # Set default currency when creating new item
        if not change:  # If creating new item
            obj.currency = 'USD'  # Set your default currency here
        super().save_model(request, obj, form, change)
    
    def order_count(self, obj):
        return obj.orderitem_set.count()
    order_count.short_description = 'Times Ordered'


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['item_display', 'quantity', 'unit_price', 'total_price_display']
    can_delete = False
    max_num = 0
    
    def item_display(self, obj):
        return obj.item.name if obj.item else "No Item"
    item_display.short_description = 'Item Name'
    
    def total_price_display(self, obj):
        # Handle None values safely
        if obj.quantity is None or obj.unit_price is None:
            return "N/A"
        try:
            total = obj.quantity * obj.unit_price
            # Get currency from the order
            currency_symbol = '€' if obj.order.order_currency == 'EUR' else '$'
            return f"{currency_symbol}{total:.2f}"
        except (TypeError, ValueError):
            return "Error"
    total_price_display.short_description = 'Total Price'

class OrderItemAdmin(admin.ModelAdmin):
    list_display = [
        'order_display',
        'item_display', 
        'quantity', 
        'unit_price', 
        'total_price_display',
        'currency_display',  # Add currency column
        'created_display'
    ]
    list_filter = [
        'order__payment_status',
        'order__order_currency',  # Add currency filter
        'item',
    ]
    search_fields = [
        'order__id',
        'item__name',
    ]
    readonly_fields = ['order', 'item', 'quantity', 'unit_price']
    list_per_page = 50
    
    def order_display(self, obj):
        return f"Order {str(obj.order.id)[:8]}..." if obj.order else "No Order"
    order_display.short_description = 'Order ID'
    order_display.admin_order_field = 'order__id'
    
    def item_display(self, obj):
        return obj.item.name if obj.item else "No Item"
    item_display.short_description = 'Item Name'
    item_display.admin_order_field = 'item__name'
    
    def total_price_display(self, obj):
        # Handle None values safely
        if obj.quantity is None or obj.unit_price is None:
            return "N/A"
        try:
            total = obj.quantity * obj.unit_price
            # Get currency from the order
            currency_symbol = '€' if obj.order.order_currency == 'EUR' else '$'
            return f"{currency_symbol}{total:.2f}"
        except (TypeError, ValueError):
            return "Error"
    total_price_display.short_description = 'Total Price'
    
    def currency_display(self, obj):
        return obj.order.order_currency if obj.order else "N/A"
    currency_display.short_description = 'Currency'
    currency_display.admin_order_field = 'order__order_currency'
    
    def created_display(self, obj):
        return obj.order.created_at.strftime("%Y-%m-%d %H:%M") if obj.order else "N/A"
    created_display.short_description = 'Order Date'
    created_display.admin_order_field = 'order__created_at'

class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id_short',
        'payment_status_badge',
        'order_currency',
        'total_with_currency',  # Changed from 'total' to show currency symbol
        'stripe_payment_intent_id_short',
        'created_at'
    ]
    list_filter = [
        'payment_status',
        'order_currency', 
        'created_at'
    ]
    search_fields = [
        'id',
        'stripe_payment_intent_id'
    ]
    readonly_fields = [
        'id',
        'created_at',
        'stripe_payment_intent_id',
        'subtotal',
        'discount_amount', 
        'tax_amount',
        'total'
    ]
    list_per_page = 50
    inlines = [OrderItemInline]
    actions = ['mark_as_completed', 'mark_as_cancelled']
    
    def id_short(self, obj):
        return str(obj.id)[:8] + '...'
    id_short.short_description = 'Order ID'
    
    def payment_status_badge(self, obj):
        status_colors = {
            Order.PAYMENT_PENDING: 'orange',
            Order.PAYMENT_COMPLETE: 'green',
            Order.PAYMENT_FAILED: 'red',
            Order.PAYMENT_CANCELLED: 'gray',
        }
        color = status_colors.get(obj.payment_status, 'blue')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px;">{}</span>',
            color,
            obj.get_payment_status_display()
        )
    payment_status_badge.short_description = 'Payment Status'
    
    def total_with_currency(self, obj):
        """Display total with appropriate currency symbol"""
        currency_symbol = '€' if obj.order_currency == 'EUR' else '$'
        return f"{currency_symbol}{obj.total:.2f}"
    total_with_currency.short_description = 'Total'
    total_with_currency.admin_order_field = 'total'
    
    def stripe_payment_intent_id_short(self, obj):
        if obj.stripe_payment_intent_id:
            return obj.stripe_payment_intent_id[:20] + '...' if len(obj.stripe_payment_intent_id) > 20 else obj.stripe_payment_intent_id
        return "No ID"
    stripe_payment_intent_id_short.short_description = 'Stripe ID'
    
    def mark_as_completed(self, request, queryset):
        updated = queryset.update(payment_status=Order.PAYMENT_COMPLETE)
        self.message_user(request, f'{updated} orders marked as completed.')
    mark_as_completed.short_description = "Mark selected orders as completed"
    
    def mark_as_cancelled(self, request, queryset):
        updated = queryset.update(payment_status=Order.PAYMENT_CANCELLED)
        self.message_user(request, f'{updated} orders marked as cancelled.')
    mark_as_cancelled.short_description = "Mark selected orders as cancelled"
    
class DiscountAdmin(admin.ModelAdmin):
    list_display = ['name', 'percentage', 'is_active']
    list_editable = ['is_active']
    list_filter = ['is_active']

class TaxAdmin(admin.ModelAdmin):
    list_display = ['name', 'percentage', 'is_active']
    list_editable = ['is_active']
    list_filter = ['is_active']




# Custom Admin View for Dashboard
class CustomAdminSite(admin.AdminSite):
    site_header = "E-Commerce Admin Dashboard"
    site_title = "E-Commerce Admin"
    index_title = "Dashboard Overview"
    
    def index(self, request, extra_context=None):
        # Add dashboard statistics to the context
        extra_context = extra_context or {}
        
        # Basic statistics
        total_items = Item.objects.count()
        total_orders = Order.objects.count()
        total_completed_orders = Order.objects.filter(payment_status=Order.PAYMENT_COMPLETE).count()
        total_revenue = Order.objects.filter(
            payment_status=Order.PAYMENT_COMPLETE
        ).aggregate(total=Sum('total'))['total'] or 0
        
        # Recent orders
        recent_orders = Order.objects.all().order_by('-created_at')[:10]
        
        # Order status breakdown
        status_breakdown = Order.objects.values('payment_status').annotate(
            count=Count('id')
        ).order_by('payment_status')
        
        extra_context.update({
            'total_items': total_items,
            'total_orders': total_orders,
            'total_completed_orders': total_completed_orders,
            'total_revenue': total_revenue,
            'recent_orders': recent_orders,
            'status_breakdown': status_breakdown,
        })
        
        return super().index(request, extra_context)

# Register models with custom admin site
admin_site = CustomAdminSite(name='custom_admin')
admin.site.register(OrderItem, OrderItemAdmin)  # Add this line
admin_site.register(Item, ItemAdmin)
admin_site.register(Order, OrderAdmin)
admin_site.register(Discount, DiscountAdmin)
admin_site.register(Tax, TaxAdmin)

admin_site.register(User)
admin_site.register(Group)

# Register with default admin site
admin.site.register(Item, ItemAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(Discount, DiscountAdmin)
admin.site.register(Tax, TaxAdmin)