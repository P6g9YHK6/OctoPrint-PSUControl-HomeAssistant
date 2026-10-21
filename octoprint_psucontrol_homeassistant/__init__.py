# coding=utf-8
from __future__ import absolute_import

__author__ = "Erik de Keijzer <erik.de.keijzer@gmail.com>"
__license__ = "GNU Affero General Public License http://www.gnu.org/licenses/agpl.html"
__copyright__ = "Copyright (C) 2021 Erik de Keijzer - Released under terms of the AGPLv3 License"

import json
import threading
import time

import octoprint.plugin
import requests

try:
    import urllib3
    from urllib3.exceptions import InsecureRequestWarning
except ImportError:
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    import requests.packages.urllib3 as urllib3

urllib3.disable_warnings(InsecureRequestWarning)

try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

REQUEST_TIMEOUT = 10
WS_RECONNECT_MIN_DELAY = 2
WS_RECONNECT_MAX_DELAY = 60


class PSUControl_HomeAssistant(octoprint.plugin.StartupPlugin,
                         octoprint.plugin.ShutdownPlugin,
                         octoprint.plugin.RestartNeedingPlugin,
                         octoprint.plugin.TemplatePlugin,
                         octoprint.plugin.SettingsPlugin):

    def __init__(self):
        self.config = dict()
        self._state_lock = threading.Lock()
        self._last_known_state = None
        self._ws = None
        self._ws_thread = None
        self._ws_connected = False
        self._ws_stop = threading.Event()

    def get_settings_defaults(self):
        return dict(
            address = '',
            api_key = '',
            entity_id = '',
            verify_certificate = True,
            connection_lost_action = False,
            use_websocket = True,
        )

    def on_settings_initialized(self):
        self.reload_settings()

    def reload_settings(self):
        for k, v in self.get_settings_defaults().items():
            if type(v) == str:
                v = self._settings.get([k])
            elif type(v) == int:
                v = self._settings.get_int([k])
            elif type(v) == float:
                v = self._settings.get_float([k])
            elif type(v) == bool:
                v = self._settings.get_boolean([k])

            self.config[k] = v
            self._logger.debug("{}: {}".format(k, v))

    def on_startup(self, host, port):
        psucontrol_helpers = self._plugin_manager.get_helpers("psucontrol")
        if not psucontrol_helpers or 'register_plugin' not in psucontrol_helpers.keys():
            self._logger.warning("The version of PSUControl that is installed does not support plugin registration.")
            return

        self._logger.debug("Registering plugin with PSUControl")
        psucontrol_helpers['register_plugin'](self)

    def on_after_startup(self):
        self._start_websocket_if_enabled()

    def on_shutdown(self):
        self._stop_websocket()

    #
    # REST
    #

    def send(self, cmd, data=None):
        address = self.config.get('address', '').rstrip('/')
        if not address:
            self._logger.error("Home Assistant address is not configured.")
            return None

        api_key = self.config.get('api_key', '')
        if not api_key:
            self._logger.warning("No Home Assistant API key configured.")

        url = address + '/api' + cmd
        headers = dict(Authorization='Bearer ' + api_key)
        verify_certificate = self.config.get('verify_certificate', True)

        response = None
        try:
            if data is not None:
                response = requests.post(url, headers=headers, json=data, verify=verify_certificate, timeout=REQUEST_TIMEOUT)
            else:
                response = requests.get(url, headers=headers, verify=verify_certificate, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.Timeout:
            self._logger.error("Timed out waiting for a response from Home Assistant.")
        except (
                requests.exceptions.InvalidURL,
                requests.exceptions.ConnectionError
        ):
            self._logger.error("Unable to communicate with server. Check settings.")
        except Exception:
            self._logger.exception("Exception while making API call")
        else:
            if data is not None:
                self._logger.debug("cmd={}, data={}, status_code={}, text={}".format(cmd, data, response.status_code, response.text))
            else:
                self._logger.debug("cmd={}, status_code={}, text={}".format(cmd, response.status_code, response.text))

            if response.status_code == 401:
                self._logger.warning("Server returned 401 Unauthorized. Check API key.")
                response = None
            elif response.status_code == 404:
                self._logger.warning("Server returned 404 Not Found. Check Entity ID.")
                response = None

        return response

    def _normalized_entity_id(self):
        _entity_id = self.config.get('entity_id', '')
        if not _entity_id:
            return None
        if '.' not in _entity_id:
            return 'switch.' + _entity_id
        return _entity_id

    def change_psu_state(self, turn_on):
        _entity_id = self._normalized_entity_id()
        if not _entity_id:
            self._logger.error("Home Assistant entity ID is not configured.")
            return

        _domain = _entity_id.split('.')[0]
        # Groups don't have turn_on/off services
        if _domain == 'group':
            _domain = 'homeassistant'

        cmd = '/services/' + _domain + '/turn_' + ('on' if turn_on else 'off')
        self.send(cmd, dict(entity_id=_entity_id))

    def turn_psu_on(self):
        self._logger.debug("Switching PSU On")
        self.change_psu_state(True)

    def turn_psu_off(self):
        self._logger.debug("Switching PSU Off")
        self.change_psu_state(False)

    def _get_psu_state_rest(self):
        """Returns True/False for a determined state, or None if the state could not be determined."""
        _entity_id = self._normalized_entity_id()
        if not _entity_id:
            self._logger.error("Home Assistant entity ID is not configured.")
            return None

        response = self.send('/states/' + _entity_id)
        if not response:
            return None

        try:
            data = response.json()
        except ValueError:
            self._logger.error("Unable to parse Home Assistant response as JSON.")
            return None

        try:
            return data['state'] == 'on'
        except KeyError:
            return None

    def get_psu_state(self):
        if self.config.get('use_websocket') and self._ws_connected:
            with self._state_lock:
                if self._last_known_state is not None:
                    return self._last_known_state
            # Connected but no event observed yet, fall through to a one-off REST lookup.

        status = self._get_psu_state_rest()

        if status is None:
            if self.config.get('connection_lost_action'):
                with self._state_lock:
                    if self._last_known_state is not None:
                        self._logger.warning("Unable to determine status from Home Assistant, returning last known state.")
                        return self._last_known_state
            self._logger.error("Unable to determine status. Check settings.")
            return False

        with self._state_lock:
            self._last_known_state = status

        return status

    #
    # WebSocket (live push sensing, falls back to REST polling above when unavailable)
    #

    def _ws_url(self):
        address = self.config.get('address', '').rstrip('/')
        if address.startswith('https://'):
            return 'wss://' + address[len('https://'):] + '/api/websocket'
        elif address.startswith('http://'):
            return 'ws://' + address[len('http://'):] + '/api/websocket'
        return None

    def _start_websocket_if_enabled(self):
        if not self.config.get('use_websocket'):
            return

        if not HAS_WEBSOCKET:
            self._logger.warning("The 'websocket-client' package is not installed, falling back to REST polling. Run 'pip install websocket-client' in OctoPrint's environment to enable live updates.")
            return

        if not self.config.get('address') or not self.config.get('api_key') or not self.config.get('entity_id'):
            self._logger.debug("Home Assistant address, API key or entity ID not configured, skipping WebSocket.")
            return

        self._ws_stop.clear()
        self._ws_thread = threading.Thread(target=self._ws_run_loop, name="psucontrol_homeassistant_ws", daemon=True)
        self._ws_thread.start()

    def _stop_websocket(self):
        self._ws_stop.set()
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
        if self._ws_thread is not None:
            self._ws_thread.join(timeout=5)

    def _ws_run_loop(self):
        delay = WS_RECONNECT_MIN_DELAY
        while not self._ws_stop.is_set():
            url = self._ws_url()
            if not url:
                return

            self._ws = websocket.WebSocketApp(
                url,
                on_open=self._ws_on_open,
                on_message=self._ws_on_message,
                on_error=self._ws_on_error,
                on_close=self._ws_on_close,
            )

            sslopt = None
            if not self.config.get('verify_certificate', True):
                import ssl
                sslopt = {"cert_reqs": ssl.CERT_NONE}

            try:
                self._ws.run_forever(sslopt=sslopt, ping_interval=20, ping_timeout=10)
            except Exception:
                self._logger.exception("Exception in Home Assistant WebSocket connection")

            self._ws_connected = False

            if self._ws_stop.is_set():
                return

            self._logger.debug("Home Assistant WebSocket disconnected, reconnecting in {}s".format(delay))
            self._ws_stop.wait(delay)
            delay = min(delay * 2, WS_RECONNECT_MAX_DELAY)

    def _ws_on_open(self, ws):
        self._logger.debug("Home Assistant WebSocket connection opened")

    def _ws_on_error(self, ws, error):
        self._logger.debug("Home Assistant WebSocket error: {}".format(error))

    def _ws_on_close(self, ws, close_status_code, close_msg):
        self._logger.debug("Home Assistant WebSocket closed: {} {}".format(close_status_code, close_msg))
        self._ws_connected = False

    def _ws_on_message(self, ws, message):
        try:
            msg = json.loads(message)
        except ValueError:
            return

        msg_type = msg.get('type')

        if msg_type == 'auth_required':
            ws.send(json.dumps(dict(type='auth', access_token=self.config.get('api_key', ''))))
            return

        if msg_type == 'auth_invalid':
            self._logger.error("Home Assistant rejected the WebSocket access token, disabling live updates for this connection. Falling back to REST polling.")
            self._ws_connected = False
            ws.close()
            return

        if msg_type == 'auth_ok':
            self._logger.info("Home Assistant WebSocket authenticated, subscribing to state changes.")
            ws.send(json.dumps(dict(id=1, type='subscribe_events', event_type='state_changed')))
            self._ws_connected = True

            # Seed state immediately so there's no gap before the first event arrives.
            status = self._get_psu_state_rest()
            if status is not None:
                with self._state_lock:
                    self._last_known_state = status
            return

        if msg_type == 'event':
            event = msg.get('event', {})
            if event.get('event_type') != 'state_changed':
                return

            data = event.get('data', {})
            _entity_id = self._normalized_entity_id()
            if not _entity_id or data.get('entity_id') != _entity_id:
                return

            new_state = data.get('new_state')
            if not new_state:
                return

            with self._state_lock:
                self._last_known_state = (new_state.get('state') == 'on')
            return

    #
    # OctoPrint plugin hooks
    #

    def on_settings_save(self, data):
        octoprint.plugin.SettingsPlugin.on_settings_save(self, data)
        self.reload_settings()
        self._stop_websocket()
        self._start_websocket_if_enabled()

    def get_settings_version(self):
        return 1

    def on_settings_migrate(self, target, current=None):
        pass

    def get_template_configs(self):
        return [
            dict(type="settings", custom_bindings=False)
        ]

    def get_update_information(self):
        return dict(
            psucontrol_homeassistant=dict(
                displayName="PSU Control - Home Assistant",
                displayVersion=self._plugin_version,

                # version check: github repository
                type="github_release",
                user="P6g9YHK6",
                repo="OctoPrint-PSUControl-HomeAssistant",
                current=self._plugin_version,

                # update method: pip w/ dependency links
                pip="https://github.com/P6g9YHK6/OctoPrint-PSUControl-HomeAssistant/archive/{target_version}.zip"
            )
        )

__plugin_name__ = "PSU Control - Home Assistant"
__plugin_pythoncompat__ = ">=3,<4"

def __plugin_load__():
    global __plugin_implementation__
    __plugin_implementation__ = PSUControl_HomeAssistant()

    global __plugin_hooks__
    __plugin_hooks__ = {
        "octoprint.plugin.softwareupdate.check_config": __plugin_implementation__.get_update_information
    }
