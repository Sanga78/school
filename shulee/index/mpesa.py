import base64
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.utils import timezone


class MpesaError(Exception):
    pass


def _base_url():
    if settings.MPESA_ENVIRONMENT == 'production':
        return 'https://api.safaricom.co.ke'
    if settings.MPESA_ENVIRONMENT == 'sandbox':
        return 'https://sandbox.safaricom.co.ke'
    raise MpesaError('M-Pesa environment must be sandbox or production.')


def _credentials():
    values = (
        settings.MPESA_CONSUMER_KEY,
        settings.MPESA_CONSUMER_SECRET,
        settings.MPESA_SHORTCODE,
        settings.MPESA_PASSKEY,
        settings.MPESA_CALLBACK_URL,
    )
    if not all(values):
        raise MpesaError('M-Pesa payment is not configured. Contact the school bursar.')
    if not settings.MPESA_CALLBACK_URL.startswith('https://'):
        raise MpesaError('M-Pesa requires a public HTTPS callback URL.')
    return values


def _request_json(url, data=None, headers=None):
    request = Request(
        url,
        data=json.dumps(data).encode('utf-8') if data is not None else None,
        headers=headers or {},
        method='POST' if data is not None else 'GET',
    )
    try:
        with urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise MpesaError('Could not reach M-Pesa. Please try again later.') from error
    if not isinstance(payload, dict):
        raise MpesaError('M-Pesa returned an invalid response.')
    return payload


def _access_token():
    consumer_key, consumer_secret, _, _, _ = _credentials()
    credentials = base64.b64encode(
        f'{consumer_key}:{consumer_secret}'.encode('utf-8')
    ).decode('ascii')
    query = urlencode({'grant_type': 'client_credentials'})
    response = _request_json(
        f'{_base_url()}/oauth/v1/generate?{query}',
        headers={'Authorization': f'Basic {credentials}'},
    )
    token = response.get('access_token')
    if not isinstance(token, str) or not token:
        raise MpesaError('M-Pesa did not return an access token.')
    return token


def initiate_stk_push(*, phone_number, amount, account_reference, transaction_desc):
    _, _, shortcode, passkey, callback_url = _credentials()
    timestamp = timezone.localtime().strftime('%Y%m%d%H%M%S')
    password = base64.b64encode(
        f'{shortcode}{passkey}{timestamp}'.encode('utf-8')
    ).decode('ascii')
    payload = {
        'BusinessShortCode': shortcode,
        'Password': password,
        'Timestamp': timestamp,
        'TransactionType': 'CustomerPayBillOnline',
        'Amount': amount,
        'PartyA': phone_number,
        'PartyB': shortcode,
        'PhoneNumber': phone_number,
        'CallBackURL': callback_url,
        'AccountReference': account_reference[:12],
        'TransactionDesc': transaction_desc[:13],
    }
    response = _request_json(
        f'{_base_url()}/mpesa/stkpush/v1/processrequest',
        data=payload,
        headers={
            'Authorization': f'Bearer {_access_token()}',
            'Content-Type': 'application/json',
        },
    )
    if response.get('ResponseCode') != '0':
        raise MpesaError(response.get('ResponseDescription') or 'M-Pesa could not start the payment.')
    return response


def query_stk_push(checkout_request_id):
    _, _, shortcode, passkey, _ = _credentials()
    timestamp = timezone.localtime().strftime('%Y%m%d%H%M%S')
    password = base64.b64encode(
        f'{shortcode}{passkey}{timestamp}'.encode('utf-8')
    ).decode('ascii')
    payload = {
        'BusinessShortCode': shortcode,
        'Password': password,
        'Timestamp': timestamp,
        'CheckoutRequestID': checkout_request_id,
    }
    return _request_json(
        f'{_base_url()}/mpesa/stkpushquery/v1/query',
        data=payload,
        headers={
            'Authorization': f'Bearer {_access_token()}',
            'Content-Type': 'application/json',
        },
    )
