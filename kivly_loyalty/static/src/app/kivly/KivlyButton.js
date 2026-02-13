/** @odoo-module */

import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { KivlyModal } from "@kivly_loyalty/app/kivly/KivlyModal";

/**
 * Patch ControlButtons to add the Kivly loyalty button.
 */
patch(ControlButtons.prototype, {
    onClickKivly() {
        const order = this.pos.getOrder();
        const partner = order?.getPartner();

        this.dialog.add(KivlyModal, {
            partner: partner,
            order: order,
            pos: this.pos,
        });
    },
});
