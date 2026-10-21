> [!NOTE]
> This is a maintained fork of [edekeijzer/OctoPrint-PSUControl-HomeAssistant](https://github.com/edekeijzer/OctoPrint-PSUControl-HomeAssistant), which is no longer maintained upstream. Fixes a bug where a stalled request to Home Assistant could hang the sensing loop forever, adds optional WebSocket-based live state updates, and adds a "return last known state" option for brief connection drops.

# OctoPrint PSU Control - Home Assistant
Adds Home Assistant support to OctoPrint-PSUControl as a sub-plugin

## Setup
- Install the plugin using Plugin Manager from Settings, or from this repository's URL
- Configure this plugin
- Select this plugin as Switching *and* Sensing method in [PSU Control](https://github.com/kantlivelong/OctoPrint-PSUControl)
- :warning: **Turn off** the *Automatically turn PSU ON* option in the PSU Control settings, leaving this on will ruin your prints when Home Assistant becomes unavailable :warning: (some explanation in tickets
[#4](https://github.com/edekeijzer/OctoPrint-PSUControl-HomeAssistant/issues/4),
[#11](https://github.com/edekeijzer/OctoPrint-PSUControl-HomeAssistant/issues/11),
[#16](https://github.com/edekeijzer/OctoPrint-PSUControl-HomeAssistant/issues/16))

## Configuration
* Enter the URL of your Home Assistant Installation
* Go to your Home Assistant profile
* At the bottom, go to *Long-Lived Access Tokens*
* Click *Create Token*, give the token a name (suggestion: OctoPrint PSUControl) and click *OK*
* Copy the token and paste it into the *Access token* field in the plugin settings
* At *Entity ID* enter the ID of the Home Assistant entity you want to control (for example: *switch.my_smart_outlet*)
* If your HA installation is running HTTPS with a self-signed certificate, uncheck the *Verify certificate* option
* **Use WebSocket for live updates** (new, on by default): subscribes to the entity's state over a persistent WebSocket connection instead of polling REST on every sense interval, and automatically falls back to REST if the connection drops. Requires the `websocket-client` Python package (installed automatically as a dependency).
* **Return last known state if Home Assistant is unreachable** (new, off by default): when a REST request fails, return the last confirmed state instead of reporting the PSU as off.

## What changed in this fork
* All REST requests now use a 10s timeout. Previously a stalled request (HA restarting, a half-open connection, etc.) could block the sensing thread forever, freezing `isPSUOn` at a stale value until OctoPrint was restarted.
* Added WebSocket-based live sensing with automatic REST fallback.
* Added an option to return the last known state instead of `off` on a transient connection failure.
* Defensive handling of missing/empty configuration and non-JSON responses.

## Support
Please check your logs first. If they do not explain your issue, open an issue in GitHub. Please set *octoprint.plugins.psucontrol* and *octoprint.plugins.psucontrol_homeassistant* to **DEBUG** and include the relevant logs. Feature requests are welcome as well.

## Todo
- [x] Add descriptions to settings page
- [ ] Add images to documentation
