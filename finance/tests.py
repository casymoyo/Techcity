import json
from django.urls import reverse
from django.test import TestCase, Client
from .models import Customer, CustomerAccount, CustomerAccountBalances, Currency


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
