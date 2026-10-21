$(function () {
    var $btn = $("#psucontrol_ha_test_btn");
    var $result = $("#psucontrol_ha_test_result");
    var $browseBtn = $("#psucontrol_ha_browse_btn");
    var $entitySelect = $("#psucontrol_ha_entity_select");
    var $entityInput = $("#psucontrol_ha_entity_id");

    if (!$btn.length) {
        return;
    }

    $btn.on("click", function (e) {
        e.preventDefault();

        $result.text("Testing...").removeClass("text-success text-error");

        var payload = {
            address: $("#psucontrol_ha_address").val(),
            api_key: $("#psucontrol_ha_api_key").val(),
            entity_id: $("#psucontrol_ha_entity_id").val(),
            verify_certificate: $("#psucontrol_ha_verify_certificate").is(":checked")
        };

        OctoPrint.simpleApiCommand("psucontrol_homeassistant", "testConnection", payload)
            .done(function (response) {
                $result
                    .text(response.message)
                    .removeClass("text-success text-error")
                    .addClass(response.success ? "text-success" : "text-error");
            })
            .fail(function () {
                $result
                    .text("Request failed, check the OctoPrint log.")
                    .removeClass("text-success")
                    .addClass("text-error");
            });
    });

    $browseBtn.on("click", function (e) {
        e.preventDefault();

        $browseBtn.text("Loading...").prop("disabled", true);
        $entitySelect.hide();

        var payload = {
            address: $("#psucontrol_ha_address").val(),
            api_key: $("#psucontrol_ha_api_key").val(),
            verify_certificate: $("#psucontrol_ha_verify_certificate").is(":checked")
        };

        OctoPrint.simpleApiCommand("psucontrol_homeassistant", "getDevices", payload)
            .done(function (response) {
                $browseBtn.text("Browse...").prop("disabled", false);

                if (!response.success) {
                    $result.text(response.message).removeClass("text-success").addClass("text-error");
                    return;
                }

                $entitySelect.empty();
                $entitySelect.append($("<option>").val("").text("-- " + response.devices.length + " entities found, pick one --"));
                response.devices.forEach(function (device) {
                    $entitySelect.append(
                        $("<option>")
                            .val(device.entity_id)
                            .text(device.entity_id + " (" + device.friendly_name + ") [" + device.state + "]")
                    );
                });
                $entitySelect.show();
            })
            .fail(function () {
                $browseBtn.text("Browse...").prop("disabled", false);
                $result.text("Request failed, check the OctoPrint log.").removeClass("text-success").addClass("text-error");
            });
    });

    $entitySelect.on("change", function () {
        var value = $entitySelect.val();
        if (value) {
            $entityInput.val(value).trigger("change");
        }
    });
});
