"""Poolsync account."""
from __future__ import annotations
from typing import List

import logging
from typing import Any, Final
from urllib.parse import urljoin

import requests

from .exceptions import PoolsyncApiException, PoolsyncAuthenticationError
from .utils import decode, redact
import json as jsonLib

_LOGGER = logging.getLogger(__name__)

BASE_URL: Final = "https://lsx6q9luzh.execute-api.us-east-1.amazonaws.com/api/app/"

class PoolsyncDevice:
    def __init__(self, hub_id: str, device_index: int, device_type: str, device_name: str | None = ""):
        self.hub_id: str = hub_id
        self.device_index: str = device_index
        self.device_type: str = device_type
        self.device_name: str | None = device_name 

class PoolSyncChlorsyncSWG(PoolsyncDevice):
    def __init__(self, hub_id: str, device_index: int, device_type: str, device_name: str | None, chlor_output: int, water_temp: int, salt_level: int, flow_rate: int):
        PoolsyncDevice.__init__(self, hub_id=hub_id, device_index=device_index, device_type=device_type, device_name=device_name)

        self.chlor_output = chlor_output
        self.water_temp = water_temp
        self.salt_level = salt_level
        self.flow_rate = flow_rate

class Poolsync:
    """Poolsync account."""

    def __init__(
        self,
        *,
        username: str | None = None,
        access_token: str | None = None,
        refresh_token: str | None = None,
    ) -> None:
        """Initialize."""
        self._username = username
        self._access_token = access_token
        self._refresh_token = refresh_token

    @property
    def access_token(self) -> str | None:
        """Return the access token."""
        return self._access_token

    @property
    def refresh_token(self) -> str | None:
        """Return the refresh token."""
        return self._refresh_token
    
    
    def get_all_hub_devices(self) -> list[PoolsyncDevice]:
        """Get devices for an account."""
        devices = []
        raw_devices_from_api = self.__get("things/me/devices")
    
        for j in range(0, len(raw_devices_from_api)):
            hub_id = raw_devices_from_api[j]['poolSync']['system']['macAddr']
            for i in range(0, 16):
                if raw_devices_from_api[j]['deviceType'][str(i)] != "":
                    match raw_devices_from_api[j]['deviceType'][str(i)]:
                        case "chlorSync":
                            devices.append(PoolSyncChlorsyncSWG(
                                hub_id=hub_id,
                                device_index=i,
                                device_type=raw_devices_from_api[j]['deviceType'][str(i)],
                                device_name=raw_devices_from_api[j]['devices'][str(i)]['nodeAttr']['name'],
                                chlor_output=raw_devices_from_api[j]['devices'][str(i)]['config']['chlorOutput'],
                                water_temp=raw_devices_from_api[j]['devices'][str(i)]['status']['waterTemp'],
                                salt_level=raw_devices_from_api[j]['devices'][str(i)]['status']['saltPPM'],
                                flow_rate=raw_devices_from_api[j]['devices'][str(i)]['status']['flowRate']
                            ))
                        case _:
                            devices.append(PoolsyncDevice(
                                hub_id=hub_id,
                                device_index=i,
                                device_type=raw_devices_from_api[j]['deviceType'][str(i)]
                            ))
        return devices
    
    def get_hub_devices(self, hub_id: str) -> list[PoolsyncDevice]:
        """Get devices for based on hub_id."""
        
        devices = []
        allDevices = self.get_all_hub_devices()
        for i in range(0, len(allDevices)):
            if allDevices[i].hub_id == hub_id:
                devices.append(allDevices[i])
        return devices
    
    def get_hub_device(self, hub_id: str, device_index: int) -> PoolsyncDevice:
        """Get specific device for an account based on ID and index."""

        devices = self.get_hub_devices(hub_id);
        for i in range(0, 16): 
            if devices[i].device_index == device_index:
                return devices[i]
        return {}
            
    def __update_hub_device(self, hub_id: str, data: Any) -> Any:
        """Update device."""
        return self.__post("things/" + hub_id, data)

    def change_chlor_output(self, swg: PoolSyncChlorsyncSWG, new_output: int) -> None:
        """Change the chlor output of a salt water generator."""
        self.__update_hub_device(swg.hub_id, 
            {
                "devices": {
                    str(swg.device_index): {
                        "config": {
                            "chlorOutput": new_output
                        }
                    }
                }
            }
        )

    def refresh_tokens(self) -> None:
        """ Refresh the tokens currently in use. """

        try:
            refreshResponse = requests.request(
                "post", BASE_URL + "auth/token", headers={"Content-Type": "application/json"}, timeout=30, json={
                    "refresh": self.refresh_token
                })
            json = refreshResponse.json()

            if refreshResponse.status_code != 200:
                raise PoolsyncAuthenticationError
            else:
                self._access_token = json['tokens']['access']
        except Exception as err:
            _LOGGER.error(err)
            raise PoolsyncAuthenticationError(err) from err

    def get_tokens(self) -> dict[str, str]:
        """Return the tokens."""
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
        }

    def authenticate(self, password: str) -> None:
        """Authenticate a user. This is now done by a custom API and not Cognito."""

        try:
            loginResponse = requests.request(
                "post", BASE_URL + "auth/login", timeout=30, json={
                    "email": self._username,
                    "password": password
                }
            )
            json = loginResponse.json()

            if (loginResponse.status_code == 400) and (json.get("error") == "Incorrect username or password."):
                raise PoolsyncAuthenticationError
            else:
                self._access_token = json['tokens']['access']
                self._refresh_token = json['tokens']['refresh']
        except Exception as err:
            _LOGGER.error(err)
            raise PoolsyncAuthenticationError(err) from err
        
    def is_logged_in(self) -> bool:
        return self.access_token != None and self.refresh_token != None

    def logout(self) -> None:
        """Logout of all clients (including app)."""
        self.access_token = ""
        self.refresh_token = ""

    def __request(self, method: str, url: str, data: Any = None, should_retry: bool = True, **kwargs: Any) -> Any:
        """Make a request."""
        if (data is None):
            _LOGGER.debug("Making %s request to %s with %s", method, url, redact(kwargs))
            response = requests.request(
                method, BASE_URL + url, headers={"Authorization": self.access_token}, timeout=30, **kwargs
            )
            json = response.json()
        else:
            _LOGGER.debug("Making %s request to %s with payload of %s and with %s", method, url, data, redact(kwargs))
           
            response = requests.request(
                method, BASE_URL + url, headers={"Authorization": self.access_token, "content-type": "application/json"}, timeout=30, data=jsonLib.dumps(data), **kwargs
            )
            try: 
                json = response.json()
            except:
                json={}
        _LOGGER.debug(
            "Received %s response from %s: %s", response.status_code, url, redact(json)
        )
        if (status_code := response.status_code) == 401 and (json.get("error") == "Did not pass authentication.") and should_retry:
            _LOGGER.debug("Refreshing tokens and retrying request")
            self.refresh_tokens()
            return self.__request(method, url, data, should_retry=False, **kwargs)
        elif (status_code := response.status_code) == 401 and (json.get("error") == "Did not pass authentication.") and should_retry == False:
            _LOGGER.debug("Could not refresh token.")
            raise PoolsyncAuthenticationError
        elif (status_code := response.status_code) != 200:
            _LOGGER.error("Status: %s - %s", status_code, json)
            raise PoolsyncApiException
        return json

    def __get(self, url: str, **kwargs: Any) -> Any:
        """Make a get request."""
        return self.__request("get", url, **kwargs)

    def __post(  
        self, url: str, data, **kwargs: Any
    ) -> Any:
        """Make a post request."""
        return self.__request("post", url, data, **kwargs)

    def __put(  # pylint: disable=unused-private-member
        self, url: str, data, **kwargs: Any
    ) -> Any:
        """Make a put request."""
        return self.__request("put", url, data, **kwargs)