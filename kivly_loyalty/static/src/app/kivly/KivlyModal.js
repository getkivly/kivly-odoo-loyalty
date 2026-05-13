/** @odoo-module */

import { Component, useState, onWillUnmount } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Modal that displays the Kivly iframe.
 * Handles bidirectional communication with the iframe via postMessage.
 */
export class KivlyModal extends Component {
    static template = "kivly_loyalty.KivlyModal";
    static components = { Dialog };
    static props = {
        partner: { type: Object, optional: true },
        order: { type: Object, optional: true },
        pos: Object,
        close: Function,
    };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            error: null,
            iframeUrl: null,
        });

        this._onMessage = this._onMessage.bind(this);

        onWillUnmount(() => {
            window.removeEventListener("message", this._onMessage);
        });

        this._initialize();
    }

    async _initialize() {
        try {
            const partner = this.props.partner;

            const result = await this.orm.call("kivly.config", "get_loyalty_url", []);

            if (!result) {
                this.state.error = _t("Kivly URL not configured. Set it in Settings > Kivly.");
                this.state.loading = false;
                return;
            }

            let url = result;

            if (partner) {
                const params = new URLSearchParams();
                if (partner.kivly_id) params.append("customer_id", partner.kivly_id);
                if (partner.phone) params.append("phone", partner.phone);
                if (partner.email) params.append("email", partner.email);
                if (partner.name) params.append("name", partner.name);
                params.append("auto_open", "true");

                const separator = url.includes("?") ? "&" : "?";
                url = `${url}${separator}${params.toString()}`;
            }

            this.state.iframeUrl = url;
            this.state.loading = false;
            window.addEventListener("message", this._onMessage);
        } catch (error) {
            console.error("[Kivly] Error initializing modal:", error);
            this.state.error = _t("Error loading Kivly. Check configuration.");
            this.state.loading = false;
        }
    }

    /**
     * Handle messages from the Kivly iframe.
     * @param {MessageEvent} event
     */
    async _onMessage(event) {
        const data = event.data;

        // Ignore non-Kivly messages (browser extensions, etc.)
        if (
            !data ||
            typeof data !== "object" ||
            data.source === "react-devtools-content-script" ||
            data.source === "react-devtools-bridge" ||
            data.source === "react-devtools-inject-backend" ||
            !data.type ||
            !data.type.startsWith("KIVLY_")
        ) {
            return;
        }

        // Validate origin
        let allowedOrigin;
        try {
            allowedOrigin = new URL(this.state.iframeUrl).origin;
        } catch {
            allowedOrigin = null;
        }

        const isLocalDev =
            event.origin.includes("localhost") ||
            event.origin.includes("127.0.0.1") ||
            event.origin.startsWith("http://192.168.") ||
            event.origin.startsWith("http://10.");

        if (allowedOrigin && event.origin !== allowedOrigin && !isLocalDev) {
            return;
        }

        if (data.type === "KIVLY_REDEEM" || data.type === "KIVLY_DISCOUNT") {
            await this._handleRedeem(data);
        } else if (data.type === "KIVLY_CLOSE") {
            this.props.close();
        } else if (data.type === "KIVLY_CUSTOMER_SELECTED") {
            await this._handleCustomerSelected(data);
        }
    }

    /**
     * Handle reward redemption from the Kivly iframe.
     * Supports both fixed amount and percentage:
     * - amount: fixed discount (e.g. 5.00 for 5€)
     * - percentage: discount % of order total (e.g. 15 for 15%)
     * @param {Object} data - Redemption data with amount, percentage, reward_id, etc.
     */
    async _handleRedeem(data) {
        try {
            const order = this.props.order;
            const pos = this.props.pos;

            let amount;
            const pct = parseFloat(data.percentage);
            const amt = parseFloat(data.amount);
            if (pct > 0 && pct <= 100) {
                // Percentage: apply to the current POS order total.
                const total = order.get_total_with_tax?.() ?? 0;
                amount = Math.round((total * pct) / 100 * 100) / 100;
            } else if (amt > 0) {
                // Fixed amount
                amount = amt;
            } else {
                return;
            }

            if (amount <= 0) {
                return;
            }

            // Get the discount product ID via ORM (bypasses pos.config proxy limitations in Odoo 19)
            const configData = await this.orm.call(
                "pos.config",
                "read",
                [[pos.config.id], ["kivly_discount_product_id"]]
            );
            const rawValue = configData?.[0]?.kivly_discount_product_id;
            const discountProductId = Array.isArray(rawValue) ? rawValue[0] : rawValue;

            if (!discountProductId) {
                this.notification.add(
                    _t("Kivly discount product is not configured. Go to POS > Configuration."),
                    { type: "danger" }
                );
                return;
            }

            // Find the product in loaded POS models (loaded via _get_special_products)
            const discountProduct = pos.models["product.product"].get(discountProductId);

            if (!discountProduct) {
                this.notification.add(
                    _t("Kivly discount product not available in POS. Check configuration."),
                    { type: "danger" }
                );
                return;
            }

            // Add discount line to the current order (Odoo 19 API)
            await pos.addLineToCurrentOrder(
                {
                    product_id: discountProduct,
                    price_unit: -amount,
                    qty: 1,
                    product_tmpl_id: discountProduct.product_tmpl_id,
                },
                { merge: false }
            );

            // Link customer if available and not yet set
            if (data.customer_phone && !this.props.partner) {
                await this._linkCustomerToOrder(data);
            }

            this.props.close();

            this.notification.add(
                _t("Discount of $%s applied", amount.toFixed(2)),
                { type: "success" }
            );
        } catch (error) {
            console.error("[Kivly] Error applying discount:", error);
            this.notification.add(_t("Error: %s", error.message), { type: "danger" });
        }
    }

    /**
     * Handle customer selection from the iframe.
     * @param {Object} data - Customer data with customer_id, customer_phone
     */
    async _handleCustomerSelected(data) {
        try {
            const order = this.props.order;
            const pos = this.props.pos;

            let partnerId = null;

            if (data.customer_id) {
                const partners = await this.orm.searchRead(
                    "res.partner",
                    [["kivly_id", "=", data.customer_id]],
                    ["id"]
                );
                if (partners.length > 0) {
                    partnerId = partners[0].id;
                }
            }

            if (!partnerId && data.customer_phone) {
                const partners = await this.orm.searchRead(
                    "res.partner",
                    [["phone", "=", data.customer_phone]],
                    ["id"]
                );
                if (partners.length > 0) {
                    partnerId = partners[0].id;
                }
            }

            if (partnerId) {
                const partner = pos.models["res.partner"].get(partnerId);
                if (partner) {
                    order.set_partner(partner);
                }
            }
        } catch (error) {
            console.error("[Kivly] Error selecting customer:", error);
        }
    }

    /**
     * Try to link a customer to the current order by phone number.
     * @param {Object} data - Data containing customer_phone
     */
    async _linkCustomerToOrder(data) {
        try {
            const pos = this.props.pos;
            const partners = await this.orm.searchRead(
                "res.partner",
                [["phone", "=", data.customer_phone]],
                ["id"]
            );

            if (partners.length > 0) {
                const partner = pos.models["res.partner"].get(partners[0].id);
                if (partner) {
                    this.props.order.set_partner(partner);
                }
            }
        } catch (error) {
            console.error("[Kivly] Error linking customer:", error);
        }
    }
}
