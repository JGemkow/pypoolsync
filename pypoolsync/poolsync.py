"""Poolsync account."""
from __future__ import annotations
from datetime import datetime, timezone
from time import time
from typing import List

import logging
from typing import Any, Final
from urllib.parse import urljoin

import requests
from botocore.exceptions import ClientError
from pycognito import Cognito

from .const import CLIENT_ID, IDENTITY_POOL_ID, REGION_NAME, USER_POOL_ID
from .exceptions import PoolsyncAuthenticationError
from .utils import decode, redact
import json as jsonLib

import jwt

_LOGGER = logging.getLogger(__name__)

BASE_URL: Final = "https://cpxc1vu5ul.execute-api.us-east-1.amazonaws.com"

class PoolsyncHub:
    def __init__(self, hubId: str):
        self.hubId: str = hubId

class PoolsyncDevice:
    def __init__(self, hubId: str, deviceIndex: int, deviceType: str, deviceName: str | None = ""):
        self.hubId: str = hubId
        self.deviceIndex: str = deviceIndex
        self.deviceType: str = deviceType
        self.deviceName: str | None = deviceName 

class PoolSyncChlorsyncSWG(PoolsyncDevice):
    def __init__(self, hubId: str, deviceIndex: int, deviceType: str, deviceName: str | None, chlorOutput: int, waterTemp: int, saltLevel: int, flowRate: int):
        PoolsyncDevice.__init__(self, hubId=hubId, deviceIndex=deviceIndex, deviceType=deviceType, deviceName=deviceName)

        self.chlorOutput = chlorOutput
        self.waterTemp = waterTemp
        self.saltLevel = saltLevel
        self.flowRate = flowRate

class Poolsync:
    """Poolsync account."""

    _user: Cognito | None = None

    def __init__(
        self,
        *,
        username: str | None = None,
        access_token: str | None = None,
        id_token: str | None = None,
        refresh_token: str | None = None,
    ) -> None:
        """Initialize."""
        self._username = username
        self._access_token = access_token
        self._id_token = id_token
        self._refresh_token = refresh_token

    @property
    def access_token(self) -> str | None:
        """Return the access token."""
        return self._user.access_token if self._user else self._access_token

    @property
    def id_token(self) -> str | None:
        """Return the id token."""
        return self._user.id_token if self._user else self._id_token

    @property
    def refresh_token(self) -> str | None:
        """Return the refresh token."""
        return self._user.refresh_token if self._user else self._refresh_token
    
    def get_user_id(self) -> str:
        return jwt.decode(self._user.access_token, options={"verify_signature": False})['username']

    def get_hubs(self) -> List[PoolsyncDevice]:
        """Get hubs."""
        userName = self.get_user_id()
        rawDevicesFromAPI = self.__get("/v4/users/" + userName + "/things")
        devices = []
        for item in rawDevicesFromAPI['things']:
            devices.append(
                PoolsyncHub(
                    hubId=item
                )
            )
        return devices
    
    def get_hubdevices(self, hubId: str) -> list[PoolsyncDevice]:
        """Get devices for a hub."""
        devices = []
        rawDevicesFromAPI = self.__get("/v3/things/" + hubId)
    
        for i in range(0, 16):
            if rawDevicesFromAPI['state']['reported']['deviceType'][str(i)] != "":
                devices.append(
                    PoolsyncDevice(
                        hubId=hubId,
                        deviceIndex=i,
                        deviceType=rawDevicesFromAPI['state']['reported']['deviceType'][str(i)]
                    )
                )
        return devices

    def get_hubdevicedetails(self, device: PoolsyncDevice) -> PoolsyncDevice:
        """Get device."""
        rawDeviceFromAPI = self.__get("/v3/things/" + device.hubId + "-" + str(device.deviceIndex))

        match device.deviceType:
            case "chlorSync":
                return PoolSyncChlorsyncSWG(
                    hubId=device.hubId,
                    deviceIndex=device.deviceIndex,
                    deviceType=device.deviceType,
                    deviceName=rawDeviceFromAPI['state']['reported']['nodeAttr']['name'],
                    chlorOutput=rawDeviceFromAPI['state']['reported']['config']['chlorOutput'],
                    waterTemp=rawDeviceFromAPI['state']['reported']['status']['waterTemp'],
                    saltLevel=rawDeviceFromAPI['state']['reported']['status']['saltPPM'],
                    flowRate=rawDeviceFromAPI['state']['reported']['status']['flowRate']
                )
            case _:
                return device
            
    def __update_hubdevice(self, hubId: str, data: Any) -> Any:
        """Update device."""
        return self.__post("/v3/things/" + hubId, data)

    def change_chlor_output(self, swg: PoolSyncChlorsyncSWG, newOutput: int) -> None:
            self.__update_hubdevice(swg.hubId, {
                "state": {
                    "desired": {
                        "devices": {
                            str(swg.deviceIndex): {
                                "config": {
                                    "chlorOutput": newOutput
                                }
                            }
                        }
                    }
                }
            })

    def get_user(self) -> Cognito:
        """Return the Cognito user."""
        
        if self._user is None:
            self._user = Cognito(
                decode(USER_POOL_ID),
                decode(CLIENT_ID),
                username=self._username,
                access_token=self.access_token,
                id_token=self.id_token,
                refresh_token=self.refresh_token,
            )
            if self.access_token or self.id_token:
                try:
                    self._user.check_token()
                    self._user.verify_tokens()                    
                except ClientError as err:
                    _LOGGER.error(err)
                    raise PoolsyncAuthenticationError(err) from err
        
        return self._user

    def get_tokens(self) -> dict[str, str]:
        """Return the tokens."""
        if (user := self.get_user()).access_token:
            return {
                "access_token": user.access_token,
                "id_token": user.id_token,
                "refresh_token": user.refresh_token,
            }
        return {}

    def refresh_tokens(self) -> None:
        """ Refresh the tokens currently in use. """
        self._user.renew_access_token()

    def authenticate(self, password: str) -> None:
        """Authenticate a user."""
        
        try:
            self.get_user().authenticate(password=password)
        except ClientError as err:
            _LOGGER.error(err)
            raise PoolsyncAuthenticationError(err) from err

    def logout(self) -> None:
        """Logout of all clients (including app)."""
        self.get_user().logout()

    def __request(self, method: str, url: str, data: Any = None, shouldRetry: bool = True, **kwargs: Any) -> Any:
        """Make a request."""
        if (data == None):
            _LOGGER.debug("Making %s request to %s with %s", method, url, redact(kwargs))
            response = requests.request(
                method, BASE_URL + url, headers={"Authorization": "Bearer "+ self.access_token}, timeout=30, **kwargs
            )
            json = response.json()
        else:
            jsonData=jsonLib.dumps(data)
            _LOGGER.debug("Making %s request to %s with payload of %s and with %s", method, url, data, redact(kwargs))
           
            response = requests.request(
                method, BASE_URL + url, headers={"Authorization": "Bearer "+ self.access_token}, timeout=30, data=jsonData, **kwargs
            )
            json = response.json()
        _LOGGER.debug(
            "Received %s response from %s: %s", response.status_code, url, redact(json)
        )
        if (status_code := response.status_code) == 401 and (json.get("message") == "The incoming token has expired" or json.get("message") == "Token has expired") and shouldRetry:
            _LOGGER.debug("Refreshing tokens and retrying request")
            self.refresh_tokens()
            return self.__request(method, url, data, shouldRetry=False, **kwargs)
        elif (status_code := response.status_code) != 200:
            _LOGGER.error("Status: %s - %s", status_code, json)
            response.raise_for_status()
        return json

    def __get(self, url: str, **kwargs: Any) -> Any:
        """Make a get request."""
        return self.__request("get", url, **kwargs)

    def __post(  # pylint: disable=unused-private-member
        self, url: str, data, **kwargs: Any
    ) -> Any:
        """Make a post request."""
        return self.__request("post", url, data, **kwargs)

    def __put(  
        self, url: str, data, **kwargs: Any
    ) -> Any:
        """Make a put request."""
        return self.__request("put", url, data, **kwargs)

    def __convert_timestamp(self, _ts: float) -> datetime:
        """Convert a timestamp to a datetime."""
        return datetime.fromtimestamp(_ts / (1000 if _ts > time() else 1), timezone.utc)

