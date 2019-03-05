from datetime import datetime, timedelta
from django.conf import settings
import os
from shutil import copyfileobj
from azure.storage.blob import BlockBlobService, BlobPermissions
from google.cloud import storage
from oauth2client.service_account import ServiceAccountCredentials
import base64
from six.moves.urllib.parse import urlencode, quote

from lib import site

def save_file_obj(dest_path, file_obj, container, return_url=True):
    if settings.AZURE_STORAGE_CONNECTION_STRING:
        return _save_to_azure(dest_path, file_obj, container)
    elif settings.GOOGLE_APPLICATION_CREDENTIALS:
        return _save_to_gcp(dest_path, file_obj, container, return_url)
    else:
        return _save_to_file_system(dest_path, file_obj, container, return_url)

def list_file_obj(dir_path, container):
    if settings.GOOGLE_APPLICATION_CREDENTIALS:
        return _list_file_obj_from_gcp(dir_path, container)

def retrieve_to_file_obj(src_path, file_obj, container):
    if settings.GOOGLE_APPLICATION_CREDENTIALS:
        return _retrieve_to_file_obj_from_gcp(src_path, file_obj, container)

def _save_to_file_system(dest_path, file_obj, container, return_url):
    fqp = os.path.join(settings.MEDIA_ROOT, container, dest_path)
    if not os.path.exists(os.path.dirname(fqp)):
        os.makedirs(os.path.dirname(fqp))

    with open(fqp, 'wb+') as dest_file:
            copyfileobj(file_obj, dest_file)

    if not return_url:
        return

    uri = '{}{}/{}'.format(settings.MEDIA_URL, container, dest_path)
    return settings.INTERNAL_MEDIA_HOST + uri, site.build_full_url(uri)

def _save_to_azure(dest_path, file_obj, container):
    blob_service = BlockBlobService(connection_string=settings.AZURE_STORAGE_CONNECTION_STRING)

    blob_service.create_blob_from_stream(container, dest_path, file_obj)
    sas_token = blob_service.generate_blob_shared_access_signature(
        container,
        dest_path,
        BlobPermissions.READ,datetime.utcnow() + timedelta(hours=24*3000))
    blob_url = blob_service.make_blob_url(container, dest_path, sas_token=sas_token)
    return blob_url, blob_url

def _save_to_gcp(dest_path, file_obj, container, return_url):
    bucket, real_container_name = _gcp_bucket(container)
    blob = bucket.blob(dest_path)
    content_type = 'application/octet-stream'
    blob.upload_from_string(file_obj.read(), content_type)

    if not return_url:
        return

    blob_url = _sign_gcp_blob_url('GET', '/'+real_container_name+'/'+dest_path, content_type, datetime.utcnow() + timedelta(hours=24*3000))
    return blob_url, blob_url

def _list_file_obj_from_gcp(dir_path, container):
    bucket, _ = _gcp_bucket(container)
    return [ blob.name for blob in bucket.list_blobs(prefix=dir_path) ]

def _retrieve_to_file_obj_from_gcp(src_path, file_obj, container):
    bucket, _ = _gcp_bucket(container)
    blob = bucket.get_blob(src_path)
    if blob:
        blob.download_to_file(file_obj)

def _sign_gcp_blob_url(verb, obj_path, content_type, expiration):
    GCS_API_ENDPOINT = 'https://storage.googleapis.com'

    expiration_in_epoch = int(expiration.timestamp())
    signature_string = ('{verb}\n'
                    '{content_md5}\n'
                    '{content_type}\n'
                    '{expiration}\n'
                    '{resource}')

    signature = signature_string.format(verb=verb,
        content_md5='',
        content_type='',
        expiration=expiration_in_epoch,
        resource=obj_path)
    creds = ServiceAccountCredentials.from_json_keyfile_name(settings.GOOGLE_APPLICATION_CREDENTIALS)
    signature = creds.sign_blob(signature)[1]
    encoded_signature = base64.b64encode(signature)
    base_url= GCS_API_ENDPOINT + obj_path
    storage_account_id = creds.service_account_email

    return '{base_url}?GoogleAccessId={account_id}&Expires={expiration}&Signature={signature}'.format(base_url=base_url,
        account_id=storage_account_id,
        expiration = expiration_in_epoch,
        signature=quote(encoded_signature))

def _gcp_bucket(container_name):
    if settings.BUCKET_PREFIX:
        container_name = settings.BUCKET_PREFIX + container_name
    client = storage.Client()
    return client.bucket(container_name), container_name
