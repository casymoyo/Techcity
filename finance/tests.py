import json
from decimal import Decimal
from django.urls import reverse
from .forms import customerDepositsForm
from django.test import TestCase, Client
from django.contrib.auth.models import User
from .models import (
    Customer, 
    CustomerAccount, 
    CustomerAccountBalances, 
    Currency,
    CustomerDeposits,
    Cashbook,
    Account,
    AccountBalance
)

class CustomerViewTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = reverse('finance:add_customer')  

        # Create some test currencies
        self.currency_usd = Currency.objects.create(code='001', name='US Dollar', symbol='USD')
        self.currency_zig = Currency.objects.create(code='002', name='ZIG', symbol='ZIG')

    def test_get_customers(self):
        # Create some test customers
        Customer.objects.create(name='Casper Moyo', email='moyo@email.com', address='123 Main St', phone_number='0778587612')
        Customer.objects.create(name='Chiedza Lingani', email='lingani@example.com', address='456 hatcliff St', phone_number='0771544658')

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        # Parse the response JSON
        data = json.loads(response.content)

        # Check if the response data is correct
        self.assertEqual(len(data), 2) 
        self.assertEqual(data[0]['name'], 'Casper Moyo')
        self.assertEqual(data[1]['name'], 'Chiedza Lingani')
        
    def test_create_customer_success(self):
        # Create valid customer data
        valid_data = {
            'name': 'Casper Moyo',
            'email': 'casy@example.com',
            'address': '789 suningdale St',
            'phonenumber': '0778587612'
        }

        response = self.client.post(self.url, json.dumps(valid_data), content_type='application/json')

        # Check the response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['success'], True)
        self.assertEqual(response_data['message'], 'Customer successfully created')

        # Verify customer and account creation in the database
        self.assertTrue(Customer.objects.filter(email='casy@example.com').exists())
        created_customer = Customer.objects.get(email='casy@example.com')
        self.assertTrue(CustomerAccount.objects.filter(customer=created_customer).exists())
        self.assertEqual(CustomerAccountBalances.objects.filter(account__customer=created_customer).count(), 2)  # 2 currencies

    def test_create_customer_failure_missing_fields(self):
        invalid_data = {
            'name': ' chiedza lingani',
            'address': '123 hact St',
        }

        response = self.client.post(self.url, json.dumps(invalid_data), content_type='application/json')

        # Check the response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['success'], False)
        self.assertEqual(response_data['message'], 'Missing required fields')

    def test_create_customer_failure_existing_email(self):
        # Create an existing customer with the same email
        Customer.objects.create(name='Christian Moyo', email='chris@example.com', address='456 smurts St', phone_number='0778947474')
        
        # Try to create a new customer with the same email
        duplicate_data = {
            'name': 'Christian Moyo',
            'email': 'chris@example.com',
            'address': '789 hatfield St',
            'phonenumber': '0778587612'
        }

        response = self.client.post(self.url, json.dumps(duplicate_data), content_type='application/json')

        # Check the response
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['success'], False)
        self.assertEqual(response_data['message'], 'Customer with this email already exists')


class EditCustomerDepositTests(TestCase):
    def setUp(self):
        # Create test user, account, and deposit objects
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.client.login(username='testuser', password='12345')
        
        self.account = Account.objects.create(
            name='Test Branch USD Cash Account',
            type=Account.AccountType.CASH
        )
        
        self.account_balance = AccountBalance.objects.create(
            account=self.account,
            currency='USD',
            branch='Test Branch',
            balance=Decimal('1000.00')
        )
        
        self.customer_deposit = CustomerDeposits.objects.create(
            customer_account=self.account,
            amount=Decimal('100.00'),
            currency='USD',
            payment_method='cash',
            branch='Test Branch',
            cashier=self.user,
            payment_reference = '123',
            reason = 'purchase screen'
        )

        self.url = reverse('finance:edit_customer_deposit', args=[self.customer_deposit.id])

    def test_edit_deposit_get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'finance/customers/edit_deposit.html')
        self.assertIsInstance(response.context['form'], customerDepositsForm)

    def test_edit_deposit_successful_post(self):
        data = {
            'amount': '150.00',
            'currency': 'USD',
            'payment_method': 'cash'
        }
        response = self.client.post(self.url, data)
        self.customer_deposit.refresh_from_db()
        self.account_balance.refresh_from_db()
        cashbook_entry = Cashbook.objects.filter(
            description__contains=f'{self.customer_deposit.payment_method.upper()} deposit adjustment',
            debit=True,
            amount=Decimal('50.00')
        ).exists()
        self.assertTrue(cashbook_entry)
        self.assertEqual(self.customer_deposit.amount, Decimal('150.00'))
        self.assertEqual(self.account_balance.balance, Decimal('1050.00'))
        self.assertRedirects(response, reverse('finance:customer', args=[self.customer_deposit.customer_account.account.customer.id]))

    def test_edit_deposit_invalid_amount(self):
        data = {
            'amount': '0.00',
            'currency': 'USD',
            'payment_method': 'cash'
        }
        response = self.client.post(self.url, data)
        self.customer_deposit.refresh_from_db()
        self.account_balance.refresh_from_db()
        self.assertEqual(self.customer_deposit.amount, Decimal('100.00'))
        self.assertEqual(self.account_balance.balance, Decimal('1000.00'))
        self.assertRedirects(response, self.url)
        self.assertContains(response, 'Amount cannot be zero or negative')

    def test_edit_deposit_account_not_found(self):
        self.customer_deposit.payment_method = 'bank'
        self.customer_deposit.save()
        data = {
            'amount': '150.00',
            'currency': 'USD',
            'payment_method': 'bank'
        }
        response = self.client.post(self.url, data)
        self.customer_deposit.refresh_from_db()
        self.account_balance.refresh_from_db()
        self.assertEqual(self.customer_deposit.amount, Decimal('100.00'))
        self.assertEqual(self.account_balance.balance, Decimal('1000.00'))
        self.assertRedirects(response, self.url)
        self.assertContains(response, 'Account matching query does not exist.')

    def test_edit_deposit_negative_adjustment(self):
        data = {
            'amount': '50.00',
            'currency': 'USD',
            'payment_method': 'cash'
        }
        response = self.client.post(self.url, data)
        self.customer_deposit.refresh_from_db()
        self.account_balance.refresh_from_db()
        cashbook_entry = Cashbook.objects.filter(
            description__contains=f'{self.customer_deposit.payment_method.upper()} deposit adjustment',
            credit=True,
            amount=Decimal('50.00')
        ).exists()
        self.assertTrue(cashbook_entry)
        self.assertEqual(self.customer_deposit.amount, Decimal('50.00'))
        self.assertEqual(self.account_balance.balance, Decimal('950.00'))
        self.assertRedirects(response, reverse('finance:customer', args=[self.customer_deposit.customer_account.account.customer.id]))

