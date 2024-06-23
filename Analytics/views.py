from django.shortcuts import render
from django.http import HttpResponse
from django.db.models import Count, Sum
from django.db.models.functions import ExtractHour
from matplotlib.pyplot import pie, savefig
from django.contrib.auth.decorators import login_required
from inventory.models import ActivityLog

@login_required
def analytics(request):
    sales_logs = ActivityLog.objects.filter(action='Sale')
    sales_by_hour = sales_logs.annotate(hour=ExtractHour('invoice__issue_date')).values('hour').annotate(total_sales=Sum('invoice__id'))
    hours = [log['hour'] for log in sales_by_hour]
    sales = [log['total_sales'] for log in sales_by_hour]
    
    print(hours, sales)
    return render(request, 'finance/analytics/analytics.html')

@login_required
def sales_chart_image(request):
    top_products = ActivityLog.objects.filter(action='Sale') \
        .values('inventory__product__name') \
        .annotate(total_sales=Sum('quantity')) \
        .order_by('-total_sales')[:5]
    
    product_names = [p['inventory__product__name'] for p in top_products]
    sales_counts = [p['total_sales'] for p in top_products]
    
    pie(sales_counts, labels=product_names, autopct='%1.1f%%')
    savefig('sales_chart.png', bbox_inches='tight')

    with open('sales_chart.png', 'rb') as image_file:
        response = HttpResponse(image_file.read(), content_type='image/png')
        return response
    
@login_required
def customers_chart_image(request):
    top_customers = ActivityLog.objects.filter(action='Sale') \
        .values('invoice__customer__name') \
        .annotate(total_sales=Sum('quantity')) \
        .order_by('-total_sales')[:5]
        
    customer_names = [p['invoice__customer__name'] for p in top_customers]
    sales_counts = [p['total_sales'] for p in top_customers]
    
    pie(sales_counts, labels=customer_names, autopct='%1.1f%%')
    savefig('customers_chart.png', bbox_inches='tight')

    with open('customers_chart.png', 'rb') as image_file:
        response = HttpResponse(image_file.read(), content_type='image/png')
        return response
    

@login_required
def sales_by_hour(request):
    sales_logs = ActivityLog.objects.filter(action='sale')
    sales_by_hour = sales_logs.annotate(hour=ExtractHour('invoice__issue_date')).values('hour').annotate(total_sales=Sum('quantity'))
    hours = [log['hour'] for log in sales_by_hour]
    sales = [log['total_sales'] for log in sales_by_hour]
    
    print(hours)
    return render(request, 'sales_by_hour.html', {'hours': hours, 'sales': sales})


