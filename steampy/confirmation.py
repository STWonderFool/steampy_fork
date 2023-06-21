import enum
import json
import time
from typing import List, Iterable

import requests
from bs4 import BeautifulSoup

from steampy import guard
from steampy.exceptions import ConfirmationExpected
from steampy.login import InvalidCredentials


class Confirmation:
    def __init__(self, confirm_type, id, nonce):
        self.confirm_type = confirm_type
        self.id = id
        self.nonce = nonce


class Tag(enum.Enum):
    CONF = 'conf'
    DETAILS = 'details'
    ALLOW = 'allow'
    CANCEL = 'cancel'


class ConfirmationExecutor:
    CONF_URL = "https://steamcommunity.com/mobileconf"

    def __init__(self, identity_secret: str, my_steam_id: str, session: requests.Session) -> None:
        self._my_steam_id = my_steam_id
        self._identity_secret = identity_secret
        self._session = session

    def _send_confirmation(self, confirmation: Confirmation) -> dict:
        tag = Tag.ALLOW
        params = self._create_confirmation_params(tag.value)
        params['op'] = tag.value,
        params['cid'] = confirmation.data_confid
        params['ck'] = confirmation.data_key
        headers = {'X-Requested-With': 'XMLHttpRequest'}
        return self._session.get(self.CONF_URL + '/ajaxop', params=params, headers=headers).json()

    def allow_only_market_listings(self):
        market_confirmations = []
        confirmations = self._get_confirmations()
        for confirmation in confirmations.copy():
            if confirmation.confirm_type == 'Market Listing':
                market_confirmations.append(confirmation)
        self.send_multi_confirmations(market_confirmations)

    def allow_only_trade_offers(self):
        trade_offers = []
        confirmations = self._get_confirmations()
        for confirmation in confirmations.copy():
            if confirmation.confirm_type == 'Trade Offer':
                trade_offers.append(confirmation)
        self.send_multi_confirmations(trade_offers)

    def allow_all_confirmations(self):
        selected_confirmations = []
        confirmations = self._get_confirmations()
        for confirmation in confirmations:
            selected_confirmations.append(confirmation)
        self.send_multi_confirmations(selected_confirmations)

    def send_multi_confirmations(self, confirmations: Iterable[Confirmation]):
        tag = Tag.ALLOW
        params = self._create_confirmation_params(tag.value)
        params['op'] = tag.value
        params['cid[]'] = [i.id for i in confirmations]
        params['ck[]'] = [i.nonce for i in confirmations]
        headers = {'X-Requested-With': 'XMLHttpRequest'}
        return self._session.post(self.CONF_URL + '/multiajaxop', data=params, headers=headers)

    def _get_confirmations(self) -> List[Confirmation]:
        confirmations = []
        confirmations_page = self._fetch_confirmations_page()
        if not confirmations_page:
            return confirmations
        for confirmation in confirmations_page:
            confirm_type = confirmation['type_name']
            id = confirmation['id']
            nonce = confirmation['nonce']
            confirmations.append(Confirmation(confirm_type, id, nonce))
        return confirmations

    def _fetch_confirmations_page(self) -> requests.Response:
        tag = Tag.CONF.value
        params = self._create_confirmation_params(tag)
        headers = {'X-Requested-With': 'com.valvesoftware.android.steam.community'}
        response = self._session.get(self.CONF_URL + '/getlist', params=params, headers=headers)
        return response.json()['conf']

    def _create_confirmation_params(self, tag_string: str) -> dict:
        timestamp = int(time.time())
        confirmation_key = guard.generate_confirmation_key(self._identity_secret, tag_string, timestamp)
        android_id = guard.generate_device_id(self._my_steam_id)
        return {'p': android_id,
                'a': self._my_steam_id,
                'k': confirmation_key,
                't': timestamp,
                'm': 'android',
                'tag': tag_string}
