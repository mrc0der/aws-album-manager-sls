import json
import boto3
from botocore.exceptions import ClientError
import requests
import jinja2
import os
import zipfile
import tempfile
import uuid

ENV = dev

S3_EXP = 3600
PP_CLIENT_ID = get_secret_from_ssm(f"/album-manager/{ENV}/paypal_cleint_id")
PP_CLIENT_SECRET = get_secret_from_ssm(f"/album-manager/{ENV}}/paypal_cleint_secret")

# aws clients
DYNAMO_CLIENT = boto3.resource('dynamodb')
S3_CLIENT = boto3.client('s3')
SES_CLIENT = boto3.client('ses')
SSM_CLIENT = boto3.client('ssm')


def get_secret_from_ssm(parameter_name, with_decryption=True):
    """
    Retrieve a secret value from AWS Systems Manager Parameter Store.

    Args:
        parameter_name (str): The name of the parameter you want to retrieve.
        with_decryption (bool): Whether to decrypt the parameter value (for SecureString types).

    Returns:
        str: The value of the parameter if successful, None otherwise.
    """
    # Initialize the SSM client
    

    try:
        # Get the parameter
        response = SSM_CLIENT.get_parameter(
            Name=parameter_name,
            WithDecryption=with_decryption
        )
        # Return the parameter value
        return response['Parameter']['Value']
    except ClientError as e:
        print(f"Failed to retrieve parameter {parameter_name}: {e}")
        return None

# AWS Lambda example
def validate_request(event):
    received_signature = event['headers'].get('X-Signature')
    request_content = event['body']  # Or however you're passing the content

    # Regenerate the HMAC signature
    secret_key = "your_shared_secret_key"
    generated_signature = generate_hmac_signature(secret_key, request_content)

    # Verify if the received signature matches the generated one
    if hmac.compare_digest(received_signature, generated_signature):
        # Proceed with processing the request
        return {
            'statusCode': 200,
            'body': json.dumps('Request authenticated successfully')
        }
    else:
        # Handle authentication failure
        return {
            'statusCode': 403,
            'body': json.dumps('Authentication failed')
        }



# Initialize the Jinja2 environment
templateLoader = jinja2.FileSystemLoader(searchpath="./email_templates")
templateEnv = jinja2.Environment(loader=templateLoader)

import requests
import json
import base64
from requests.auth import HTTPBasicAuth

def verify_paypal_webhook(event, headers):
    # PayPal API endpoint for webhook verification
    verify_url = 'https://api.paypal.com/v1/notifications/verify-webhook-signature'

    # Headers from the incoming webhook event
    transmission_id = headers.get('PAYPAL-TRANSMISSION-ID')
    transmission_time = headers.get('PAYPAL-TRANSMISSION-TIME')
    cert_url = headers.get('PAYPAL-CERT-URL')
    actual_signature = headers.get('PAYPAL-TRANSMISSION-SIG')
    webhook_id = 'YOUR_WEBHOOK_ID'  # Your actual webhook ID here

    # Verification payload
    verification_payload = {
        'auth_algo': headers.get('PAYPAL-AUTH-ALGO'),
        'cert_url': cert_url,
        'transmission_id': transmission_id,
        'transmission_sig': actual_signature,
        'transmission_time': transmission_time,
        'webhook_id': webhook_id,
        'webhook_event': event
    }

    # Encode client ID and secret for basic auth
    auth = HTTPBasicAuth(PAYPAL_CLIENT_ID, PAYPAL_SECRET)

    # Send verification request to PayPal
    response = requests.post(verify_url, json=verification_payload, auth=auth)

    # Check the verification status
    if response.status_code == 200:
        verification_status = response.json().get('verification_status')
        return verification_status == 'SUCCESS'
    else:
        print(f"Failed to verify webhook signature: {response.text}")
        return False


def process_paypal_order(event):
    # Parse the webhook event
    webhook_data = json.loads(event['body'])
    
    # Verify the webhook data with PayPal
    if verify_paypal_webhook(webhook_data['id']):
        # Extract necessary information
        sale_id = webhook_data['resource']['id']
        amount = webhook_data['resource']['amount']['total']
        currency = webhook_data['resource']['amount']['currency']
        state = webhook_data['resource']['state']
        custom_field = webhook_data['resource']['custom']
        
        # Process the order, e.g., update order status in your database, send email confirmation, etc.
        if state == 'completed':
            # Implement your order processing logic here
            print(f"Order {sale_id} completed for {amount} {currency}")
    else:
        # Handle verification failure
        print("Failed to verify PayPal webhook")

# moved to other func
# def verify_paypal_webhook(event_id):
#     # Make a request to PayPal API to verify the webhook event
#     # This is a simplified example; you'll need to set up your PayPal API credentials and use the correct endpoint
#     response = requests.get(f'https://api.paypal.com/v1/notifications/webhooks-events/{event_id}/verify',
#                             auth=(PP_CLIENT_ID, PP_CLIENT_SECRET))
#     return response.status_code == 200

# # Mock event data for testing
# mock_event = {
#     read from paypal_example.json
# }

# process_paypal_order(mock_event)

def create_client(event, context):
    table = DYNAMO_CLIENT.Table('Clients')
    body = json.loads(event['body'])
    
    client_id = str(uuid.uuid4())  # Generate a unique clientID
    client_name = body['clientName']
    email = body['email']
    # Add other fields as necessary

    response = table.put_item(
        Item={
            'clientID': client_id,
            'clientName': client_name,
            'email': email,
            # Add other fields as necessary
        }
    )

    return {
        'statusCode': 200,
        'body': json.dumps({'clientID': client_id, 'message': 'Client created successfully'})
    }


def zip_handler(event, context):
    if not validate_request(event):
        return {
            'statusCode': 401,
            'body': json.dumps('Request not validated')
        }

    client_name = event['client_name']
    album_name = event['album_name']
    email = event['email']  # Customer email

    # Assume the album directory and zip file locations
    album_dir = f'clients/{client_name}/{album_name}/'
    zip_file_key = f'zipped-albums/{client_name}/{album_name}.zip'

    # Step 1: Zip the album
    zip_album(album_dir, zip_file_key)

    # Step 2: Store details in DynamoDB
    store_album_details_in_dynamodb(client_name, album_name, zip_file_key, email)

    # Step 3: Send an email with the download link
    send_email_with_download_link(email, zip_file_key)

def zip_album(album_dir, zip_file_key):
    # Use tempfile and zipfile to create a zip and upload to S3
    # This is a simplified placeholder - actual implementation will vary
    pass

def store_album_details_in_dynamodb(client_name, album_name, zip_file_key, email):
    table = DYNAMO_CLIENT.Table('AlbumDetails')
    response = table.put_item(
        Item={
            'clientName': client_name,
            'albumName': album_name,
            'zipFileKey': zip_file_key,
            'email': email,
            'downloadLink': f'https://s3.amazonaws.com/your-bucket-name/{zip_file_key}'  # Presigned URL generation is recommended
        }
    )
    return response

def send_email_with_download_link(email, zip_file_key):
    # Generate a presigned URL for the zip file
    presigned_url = S3_CLIENT.generate_presigned_url('get_object', Params={'Bucket': 'your-bucket-name', 'Key': zip_file_key}, ExpiresIn=3600)

    # Send an email using SES
    SES_CLIENT.send_email(
        Source='your-email@example.com',
        Destination={'ToAddresses': [email]},
        Message={
            'Subject': {'Data': 'Your Album is Ready for Download'},
            'Body': {
                'Text': {'Data': f'Hi, your album is ready. You can download it here: {presigned_url}'}
            }
        }
    )

# TODO: Ensure we have the necessary permissions in your IAM role for S3, DynamoDB, and SES operations.

def send_email_with_template(recipient, fullname, links):
    subject = "Your photos are ready"
    charset = "UTF-8"

    # Load the template from the Jinja2 environment
    template = templateEnv.get_template("photo_email_template.html")

    # Render the template with the provided data
    body_html = template.render(fullname=fullname, links=links)

    try:
        response = SES_CLIENT.send_email(
            Destination={'ToAddresses': [recipient]},
            Message={
                'Body': {
                    'Html': {
                        'Charset': charset,
                        'Data': body_html,
                    },
                },
                'Subject': {
                    'Charset': charset,
                    'Data': subject,
                },
            },
            Source="your-verified-email@example.com"  # Replace with your "From" address
        )
    except Exception as e:
        print(e)
        print("Error sending email")
        return None
    return response


def webhook_handler(event, context):
    # Parse the incoming webhook data
    webhook_data = json.loads(event['body'])
    
    # Verify the webhook data with PayPal
    if verify_paypal_webhook(webhook_data['id']):
        # Extract purchase details, e.g., photo ID or customer email
        photo_id = webhook_data['resource']['custom_id']  # This is hypothetical; adjust based on actual data
        customer_email = "customer@example.com"  # Extract from webhook data or your database
        
        # Generate a presigned URL for the photo
        presigned_url = generate_presigned_url('your-s3-bucket', photo_id)
        
        # Send the photo link to the customer via email (you'll need to implement or integrate an email service)
        send_email(customer_email, presigned_url)
        
        return {
            'statusCode': 200,
            'body': json.dumps('Webhook processed successfully')
        }
    else:
        return {
            'statusCode': 400,
            'body': json.dumps('Webhook verification failed')
        }


def generate_presigned_url(bucket_name, object_name, expiration=S3_EXP):
    try:
        response = S3_CLIENT.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket_name, 'Key': object_name},
                                                    ExpiresIn=expiration)
    except Exception as e:
        print(e)
        return None
    return response

def send_email(to_email, presigned_url):
    # Implement email sending logic here
    # This could involve using AWS SES or another email service
    pass
