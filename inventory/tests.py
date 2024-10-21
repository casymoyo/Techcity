from django.test import TestCase, Client
from django.urls import reverse
from users.models import User
from inventory.models import Supplier, Product, PurchaseOrder, PurchaseOrderItem, otherExpenses
from finance.models import *
from inventory.views import if_purchase_order_is_received
from decimal import Decimal
import json

class CreatePurchaseOrderTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Create a user for authentication
        self.user = User.objects.create_user(username='testuser', password='12345', email='test@email.com')
        self.client.login(email='test@email.com', password='12345')

        # Set up data
        self.supplier = Supplier.objects.create(name='Test Supplier')
        self.product = Product.objects.create(name='Test Product', price=Decimal('10.00'))

        # URL to create purchase order
        self.url = reverse('create_purchase_order')

    def test_get_create_purchase_order(self):
        """Test the GET request to ensure forms and initial data are loaded"""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('supplier_form', response.context)
        self.assertIn('product_form', response.context)
        self.assertIn('batch_codes', response.context)

    def test_post_create_purchase_order_success(self):
        """Test successful creation of a purchase order"""
        data = {
            'purchase_order': {
                'supplier': self.supplier.id,
                'delivery_date': '2024-12-31',
                'status': 'Pending',
                'notes': 'Test order',
                'total_cost': '100.00',
                'discount': '0.00',
                'tax_amount': '10.00',
                'other_amount': '0.00',
                'payment_method': 'Cash'
            },
            'po_items': [
                {'product': self.product.name, 'quantity': 5, 'price': '10.00', 'actualPrice': '10.00'}
            ],
            'expenses': [
                {'name': 'Shipping', 'amount': '10.00'}
            ]
        }

        response = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(PurchaseOrder.objects.filter(supplier=self.supplier).exists())
        purchase_order = PurchaseOrder.objects.get(supplier=self.supplier)
        self.assertEqual(purchase_order.total_cost, Decimal('100.00'))

        # Verify items and expenses
        self.assertEqual(PurchaseOrderItem.objects.filter(purchase_order=purchase_order).count(), 1)
        self.assertEqual(otherExpenses.objects.filter(purchase_order=purchase_order).count(), 1)

    def test_post_create_purchase_order_missing_fields(self):
        """Test failure when required fields are missing"""
        data = {
            'purchase_order': {
                'supplier': self.supplier.id,
                'delivery_date': '',
                'status': 'Pending',
                'notes': 'Test order',
                'total_cost': '100.00',
                'discount': '0.00',
                'tax_amount': '10.00',
                'other_amount': '0.00',
                'payment_method': 'Cash'
            },
            'po_items': [
                {'product': self.product.name, 'quantity': 5, 'price': '10.00', 'actualPrice': '10.00'}
            ],
            'expenses': []
        }

        response = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Missing required fields', response.json()['message'])

    def test_post_create_purchase_order_invalid_json(self):
        """Test failure when invalid JSON is sent"""
        response = self.client.post(
            self.url,
            data='Invalid JSON',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('Invalid JSON payload', response.json()['message'])

class IfPurchaseOrderIsReceivedTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.client.login(username='testuser', password='12345')
        
        self.supplier = Supplier.objects.create(name='Test Supplier')
        self.purchase_order = PurchaseOrder.objects.create(
            supplier=self.supplier,
            order_number='PO001',
            delivery_date='2024-12-31',
            total_cost=Decimal('100.00'),
            tax_amount=Decimal('10.00'),
            status='Received',
            branch=self.user.branch
        )
        
        self.currency = Currency.objects.create(name='USD', default=True)
        self.vat_rate = VATRate.objects.create(rate=Decimal('10.00'), status=True)
    
    def test_purchase_order_is_received(self):
        """Test finance records are correctly created when purchase order is received"""
        response = if_purchase_order_is_received(
            request=self.client.request(),
            purchase_order=self.purchase_order,
            tax_amount=Decimal('10.00'),
            payment_method='Cash'
        )
        
        self.assertIsNone(response)  
        
        # Assert expense was created
        expense = Expense.objects.get(purchase_order=self.purchase_order)
        self.assertEqual(expense.amount, Decimal('90.00'))  # Total cost - tax amount
        
        # Assert cashbook entry was created
        cashbook = Cashbook.objects.get(expense=expense)
        self.assertEqual(cashbook.amount, Decimal('100.00'))

        # Assert VAT transaction was created
        vat_transaction = VATTransaction.objects.get(purchase_order=self.purchase_order)
        self.assertEqual(vat_transaction.tax_amount, Decimal('10.00'))
