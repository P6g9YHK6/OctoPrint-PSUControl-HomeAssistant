> [!NOTE]
> This is a maintained fork of [edekeijzer/OctoPrint-PSUControl-HomeAssistant](https://github.com/edekeijzer/OctoPrint-PSUControl-HomeAssistant), which is no longer maintained upstream.

# OctoPrint PSU Control - Home Assistant
Adds Home Assistant support to [OctoPrint-PSUControl](https://github.com/kantlivelong/OctoPrint-PSUControl) as a sub-plugin

<img width="731" height="801" alt="image" src="https://github.com/user-attachments/assets/af28b4c6-cf13-4058-9d9e-dcbb3900d147" />

## Setup
- ~~Install the plugin using Plugin Manager from Settings,~~ or from this repository's URL
- Configure this plugin
- Select this plugin as Switching *and* Sensing method in [PSU Control](https://github.com/kantlivelong/OctoPrint-PSUControl)

## Configuration
* Enter the URL of your Home Assistant Installation
* Click "Create a Token"
* Click *Create Token* on your Home Assistant page, give the token a name (suggestion: OctoPrint PSUControl) and click *OK*
* Copy the token and paste it into the *Access token* field in the plugin settings
* At *Entity ID* select the ID of the Home Assistant entity you want to control (for example: *switch.my_smart_outlet*)
* If your HA installation is running HTTPS with a self-signed certificate, uncheck the *Verify certificate* option
* Use WebSocket for live updates: subscribes to the entity's state over a persistent WebSocket connection instead of polling REST on every sense interval, and automatically falls back to REST if the connection drops. Requires the `websocket-client` Python package (installed automatically as a dependency).
* Return last known state if Home Assistant is unreachable: when a REST request fails, return the last confirmed state instead of reporting the PSU as off.

## Support
Please check your logs first. If they do not explain your issue, open an issue in GitHub. Please set *octoprint.plugins.psucontrol* and *octoprint.plugins.psucontrol_homeassistant* to **DEBUG** and include the relevant logs. Feature requests are welcome as well.
