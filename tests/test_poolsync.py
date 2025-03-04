import time
from typing import Final
import unittest

import requests
import responses

from pypoolsync.exceptions import PoolsyncAuthenticationError
from pypoolsync.poolsync import PoolSyncChlorsyncSWG, Poolsync, PoolsyncDevice
from pypoolsync.const import BASE_URL

class PoolsyncTestCase(unittest.TestCase):
    TEST_USERNAME: Final = "test" # Mock username
    TEST_FAKEPASSWORD: Final = "testfakepassword" # Mock password
    TEST_HUBID: Final = "001122334455"

    def setUpSuccesfulAuthMockResponse(self):
        responses.add(**{
        'method'         : responses.POST,
        'url'            : f'{BASE_URL}auth/login',
        'body'           : '{"tokens": { "access": "test", "refresh": "test" }}',
        'status'         : 200,
        'content_type'   : 'application/json'
        })

    def setUpSuccesfulDevicesGetMockResponse(self, chlor_output: int = 70):
        responses.add(**{
        'method'         : responses.GET,
        'url'            : f'{BASE_URL}things/me/devices',
        'body'           : f'[{{"poolSync":{{"status":{{"online":true,"flags":0,"rssi":-57,"boardTemp":24,"dateTime":"TueMar403:42:342025","remoteUiPid":4096,"remoteUiVersion":0}},"system":{{"macAddr":"{self.TEST_HUBID}","bssid":"12:12:11:11:11:12","fwVersion":851,"hwVersion":"2.0"}},"config":{{"name":"Somewhere","setupMode":0,"serviceMode":0,"brightness":0,"timeZone":"UTC0","latitude":12.1232,"longitude":-12.1234,"optIns":4294967295,"isWatching":29017662}},"faults":0,"stats":{{"numPowerups":36,"lastEsp32ResetReason":3,"restartHistory":"00000008","cfgRamConflicts":0,"cfgNvramConflicts":0,"wifiDisconnects":1,"awsDisconnects":9,"caFileRestores":0,"certFileRestores":0,"certFlashRestores":0,"pvtkeyFileRestores":0,"pvtkeyFlashRestores":0,"certRefreshes":0,"systemRestarts":33,"iRamFreeMin":85295,"iRamMaxBlock":73728,"iRamMaxBlockMin":73728,"spiRamFreeMin":2874883,"spiRamMaxBlock":2818048,"spiRamMaxBlockMin":2818048,"minTaskStackSize":2396,"taskNameMinStack":"DEV","numAwsIotTxMessages":23376,"numAwsIotRxMessages":2046,"numDeviceOffline":1166,"lastOfflineDevPid":9729,"lastOfflineDevAddr":16,"numDeviceCmdErrResp":0,"numDeviceMsgNoResp":488610,"minRssi":-86,"maxRssi":-49,"minBoardTemp":20,"maxBoardTemp":47,"numConnectButtonPresses":0,"numServiceButtonPresses":0,"numServiceAccessButtonPresses":0,"numSetupButtonPresses":0,"numConsoleLogins":0,"numConsoleIncorrectPassword":0,"upTimeSecs":2980187,"mqttKeepAliveTimeouts":524347,"numFatFsRegenerations":0,"numDeviceInstallStableFw":0,"lastDeviceInstallStableFwPid":0}}}},"devices":{{"0":{{"nodeAttr":{{"name":"ChlorSync®","pid":9729,"nodeAddr":16,"idmpAddr":0,"online":true,"flags":0,"bootMode":2,"fwUpdProg":0,"fwUpdResult":0}},"config":{{"poolCoverCtrl":false,"chlorOutput":{chlor_output},"userSaltCalib":0,"gallons":30000,"polarityChangeTime":48}},"status":{{"flags":0,"waterTemp":18,"boostRemaining":0,"flowRate":0,"saltPPM":3060,"cellRawSaltADC":820,"cellRailVoltage":5085,"fwdCurrent":0,"revCurrent":0,"outVoltage":0}},"system":{{"drvFwVersion":123,"cellFwVersion":4,"cellHwVersion":1,"cellCalib":962,"numBlades":13,"cellSerialNum":"000000000000"}},"faults":[0],"stats":[903,242,0,3,12223928,90701119,108454064,14070329,0,0]}}}},"deviceType":{{"0":"chlorSync","1":"","2":"","3":"","4":"","5":"","6":"","7":"","8":"","9":"","10":"","11":"","12":"","13":"","14":"","15":""}}}}]',
        'status'         : 200,
        'content_type'   : 'application/json'
        })

    @responses.activate  
    def testValidAutenticate(self):
        self.setUpSuccesfulAuthMockResponse()

        poolsync = Poolsync(username=self.TEST_USERNAME)
        poolsync.authenticate(password=self.TEST_FAKEPASSWORD)

        self.assertIsNotNone(poolsync.access_token)
        self.assertIsNotNone(poolsync.refresh_token)

    @responses.activate  
    def testInvalidAutenticate(self):
        # Mock response for invalid login
        responses.add(**{
        'method'         : responses.POST,
        'url'            : f'{BASE_URL}auth/login',
        'body'           : '{"error": "Incorrect username or password." }',
        'status'         : 400,
        'content_type'   : 'application/json'
        })

        poolsync = Poolsync(username=self.TEST_USERNAME)
        with self.assertRaises(PoolsyncAuthenticationError):
            poolsync.authenticate(password=self.TEST_FAKEPASSWORD)

    @responses.activate  
    def testRefreshToken(self):
        self.setUpSuccesfulAuthMockResponse()

        # Mock response for token refresh
        responses.add(**{
        'method'         : responses.POST,
        'url'            : f'{BASE_URL}auth/token',
        'body'           : '{"tokens": { "access": "newtest" } }',
        'status'         : 200,
        'content_type'   : 'application/json'
        })

        poolsync = Poolsync(username=self.TEST_USERNAME)
        poolsync.authenticate(password=self.TEST_FAKEPASSWORD)
        self.assertEqual(poolsync.access_token, "test")
        poolsync.refresh_tokens()
        self.assertEqual(poolsync.access_token, "newtest")

    @responses.activate  
    def testGetAllHubDevices(self):
        self.setUpSuccesfulAuthMockResponse()
        self.setUpSuccesfulDevicesGetMockResponse()

        poolsync = Poolsync(username=self.TEST_USERNAME)
        poolsync.authenticate(password=self.TEST_FAKEPASSWORD)

        expected: list[PoolsyncDevice] = [
            PoolSyncChlorsyncSWG(hub_id=self.TEST_HUBID, device_index=0, device_type="chlorSync", device_name="ChlorSync®", chlor_output=70, water_temp=18, salt_level=3060, flow_rate=0)
        ]
        retrieved = poolsync.get_all_hub_devices()

        # Check that count is same, first
        self.assertEqual(len(expected), len(retrieved))
        for i in range (0, len(expected)):
            # Check that types match and properties are same
            self.assertIsInstance(retrieved[i], type(expected[i]))
            self.assertEqual(expected[i].hub_id, retrieved[i].hub_id)
            self.assertEqual(expected[i].device_index, retrieved[i].device_index)
            self.assertEqual(expected[i].device_name, retrieved[i].device_name)
            self.assertEqual(expected[i].device_type, retrieved[i].device_type)
            if type(expected[i]) == PoolSyncChlorsyncSWG:
                self.assertEqual(expected[i].chlor_output, retrieved[i].chlor_output)
                self.assertEqual(expected[i].water_temp, retrieved[i].water_temp)
                self.assertEqual(expected[i].salt_level, retrieved[i].salt_level)
                self.assertEqual(expected[i].flow_rate, retrieved[i].flow_rate)

    @responses.activate
    def testGetDevice(self):
        self.setUpSuccesfulAuthMockResponse()
        self.setUpSuccesfulDevicesGetMockResponse()

        poolsync = Poolsync(username=self.TEST_USERNAME)
        poolsync.authenticate(password=self.TEST_FAKEPASSWORD)

        expected = PoolSyncChlorsyncSWG(hub_id=self.TEST_HUBID, device_index=0, device_type="chlorSync", device_name="ChlorSync®", chlor_output=70, water_temp=18, salt_level=3060, flow_rate=0)
        retrieved = poolsync.get_hub_device(self.TEST_HUBID, 0)
        
        # Check that types match and properties are same
        self.assertIsInstance(retrieved, type(expected))
        self.assertEqual(expected.hub_id, retrieved.hub_id)
        self.assertEqual(expected.device_index, retrieved.device_index)
        self.assertEqual(expected.device_name, retrieved.device_name)
        self.assertEqual(expected.device_type, retrieved.device_type)
        if type(expected) == PoolSyncChlorsyncSWG:
            self.assertEqual(expected.chlor_output, retrieved.chlor_output)
            self.assertEqual(expected.water_temp, retrieved.water_temp)
            self.assertEqual(expected.salt_level, retrieved.salt_level)
            self.assertEqual(expected.flow_rate, retrieved.flow_rate)

    @responses.activate
    def testSetChlorinator(self):
        self.setUpSuccesfulAuthMockResponse()
        self.setUpSuccesfulDevicesGetMockResponse()

        # Mock response for posting device update
        responses.add(**{
        'method'         : responses.POST,
        'url'            : f'{BASE_URL}things/001122334455',
        'status'         : 200,
        'content_type'   : 'application/json'
        })

        poolsync = Poolsync(username=self.TEST_USERNAME)
        poolsync.authenticate(password=self.TEST_FAKEPASSWORD)

        # First, test original value
        swg = PoolSyncChlorsyncSWG(hub_id=self.TEST_HUBID, device_index=0, device_type="chlorSync", device_name="ChlorSync®", chlor_output=70, water_temp=18, salt_level=3060, flow_rate=0)
        retrieved = poolsync.get_hub_device(swg.hub_id, swg.device_index)
        self.assertEqual(retrieved.chlor_output, 70)

        # Update mock for updated data
        updated_output = 80
        self.setUpSuccesfulDevicesGetMockResponse(chlor_output=updated_output)

        poolsync.change_chlor_output(swg, updated_output)
        retrieved = poolsync.get_hub_device(swg.hub_id, swg.device_index)

        self.assertEqual(retrieved.chlor_output, updated_output)


