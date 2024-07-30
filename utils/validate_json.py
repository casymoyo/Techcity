def validate_company_registration_payload(payload):
    required_company_fields = ['name', 'description', 'address', 'domain', 'logo', 'email', 'phone_number']
    required_user_fields = ['first_name', 'last_name', 'user_name', 'email', 'phonenumber', 'password']

    for field in required_company_fields:
        if field not in payload['company_data']:
            return False, f"Missing company field: {field}"

    for field in required_user_fields:
        if field not in payload['user_data']:
            return False, f"Missing user field: {field}"

    return True, ""