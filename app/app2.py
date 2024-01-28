import streamlit as st
import os
import glob
import zipfile
import sys
import threading
import hashlib
import hmac
import base64

ENV = dev
# Base directory where albums are stored
BASE_DIR = '/Media/NAS/Clients/'
HMAC_SEC_KEY = get_secret_from_ssm(f'/album/manager/{ENV}/hmac_key')
BE_API = 'https://api.n3rd-media.com/v1'
CLIENTS_API = f"{BE_API}/clients"
ALBUMS_API = f"{BE_API}/albums"

# aws clients
SSM_CLIENT = boto3.client('ssm')


def get_clients():
    send_signed_request(CLIENTS_API)

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

def generate_hmac_signature(secret_key, message):
    message_bytes = message.encode('utf-8')
    secret_key_bytes = secret_key.encode('utf-8')
    signature = hmac.new(secret_key_bytes, message_bytes, hashlib.sha256).digest()
    signature_base64 = base64.b64encode(signature).decode('utf-8')
    return signature_base64

def send_signed_request(url, data=None, headers, type='get'):
    if headers is None:
        headers = {}

    headers['X-Signature'] = generate_hmac_signature(HMAC_SEC_KEY, data)

    if type == 'get':
        requests.get(url, headers=headers, data=data)
    elif type == 'post'
        requests.post(url, headers=headers, data=data)
    else:
        print(f"Unkown type={type}")

# Add the signature to the 'X-Signature' header for the request

class ProgressPercentage(object):
    def __init__(self, filename):
        self._filename = filename
        self._size = float(os.path.getsize(filename))
        self._seen_so_far = 0
        self._lock = threading.Lock()

    def __call__(self, bytes_amount):
        # To simplify, assume this is hooked up to a single filename.
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = (self._seen_so_far / self._size) * 100
            sys.stdout.write(
                "\r%s  %s / %s  (%.2f%%)" % (
                    self._filename, self._seen_so_far, self._size,
                    percentage))
            sys.stdout.flush()




def create_album_zip(client_name, album_name):
    album_path = os.path.join(BASE_DIR, client_name, 'albums', album_name)
    zip_path = os.path.join(BASE_DIR, client_name, 'albums', f"{album_name}.zip")

    # Creating a zip file for the album
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(album_path):
            for file in files:
                file_path = os.path.join(root, file)
                zipf.write(file_path, os.path.relpath(file_path, album_path))
    
    return zip_path




def list_albums(client_name):
    """List all albums for a given client."""
    path = os.path.join(BASE_DIR, client_name, 'albums', '*')
    return [os.path.basename(album) for album in glob.glob(path)]

def display_album_photos(client_name, album_name):
    """Display all photos in a given album."""
    album_path = os.path.join(BASE_DIR, client_name, 'albums', album_name, '*')
    photo_paths = glob.glob(album_path)
    for photo_path in photo_paths:
        st.image(photo_path, caption=os.path.basename(photo_path), use_column_width=True)

def upload_album_to_s3(client_name, album_name):
    # Upload individual photos
    album_path = os.path.join(BASE_DIR, client_name, 'albums', album_name, '*')
    photo_paths = glob.glob(album_path)
    
    for photo_path in photo_paths:
        if photo_path.endswith('.zip'):
            continue  # Skip the ZIP file in the photo upload loop
        upload_file_to_s3(photo_path, client_name, album_name)

    # Upload the ZIP file
    zip_path = os.path.join(BASE_DIR, client_name, 'albums', f"{album_name}.zip")
    if os.path.exists(zip_path):
        upload_file_to_s3(zip_path, client_name, album_name, is_zip=True)
    else:
        st.error("ZIP file does not exist. Please prepare the album first.")

def upload_file_to_s3(file_path, client_name, album_name, is_zip=False):
    file_name = os.path.basename(file_path)
    if is_zip:
        object_name = f'clients/{validate_s3_key_name(client_name)}/albums/{validate_s3_key_name(album_name)}.zip'
    else:
        object_name = f'clients/{validate_s3_key_name(client_name)}/albums/{validate_s3_key_name(album_name)}/{validate_s3_key_name(file_name)}'

    # Configure the multipart upload
    config = boto3.s3.transfer.TransferConfig(multipart_threshold=1024 * 25, max_concurrency=10,
                                              multipart_chunksize=1024 * 25, use_threads=True)

    try:
        s3.upload_file(file_path, bucket_name, object_name,
                       ExtraArgs={'ACL': 'public-read', 'ContentType': 'application/zip'},
                       Config=config,
                       Callback=ProgressPercentage(file_path))
        st.success(f"Uploaded {file_name} to S3")
    except ClientError as e:
        st.error(f"Failed to upload {file_name} to S3: {e}")


# moved to other fun
# def upload_album_to_s3(client_name, album_name):
#     """Upload all photos in the selected album to S3."""
#     album_path = os.path.join(BASE_DIR, client_name, 'albums', album_name, '*')
#     photo_paths = glob.glob(album_path)
    
#     for photo_path in photo_paths:
#         file_name = os.path.basename(photo_path)
#         object_name = f'clients/{validate_s3_key_name(client_name)}/albums/{validate_s3_key_name(album_name)}/{validate_s3_key_name(file_name)}'
#         try:
#             with open(photo_path, 'rb') as f:
#                 s3.upload_fileobj(f, bucket_name, object_name)
#             st.success(f"Uploaded {file_name} to S3")
#         except ClientError as e:
#             st.error(f"Failed to upload {file_name} to S3: {e}")

def main():
    st.title("Photo Album Manager")

    # Select client
    clients = get_clients()  # Assume this is a function that retrieves client names
    client_name = st.selectbox("Select Client", clients)

    # Select album
    if client_name:
        albums = list_albums(client_name)
        album_name = st.selectbox("Select Album", albums)

        # Display album photos
        if album_name:
            st.write(f"Displaying photos from {album_name}:")
            display_album_photos(client_name, album_name)

            # Upload button
            if st.button(f"Upload {album_name} to S3"):
                upload_album_to_s3(client_name, album_name)

if __name__ == "__main__":
    main()
