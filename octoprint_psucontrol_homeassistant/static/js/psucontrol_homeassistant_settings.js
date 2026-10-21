$(function () {
    var $btn = $("#psucontrol_ha_test_btn");
    var $result = $("#psucontrol_ha_test_result");

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
});
