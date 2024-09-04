# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json
import stripe
import frappe
from frappe import _
from frappe.utils import cint, fmt_money

from payments.payment_gateways.doctype.stripe_settings.stripe_settings import (
	get_gateway_controller,
)

no_cache = 1

expected_keys = (
	"amount",
	"title",
	"description",
	"reference_doctype",
	"reference_docname",
	"payer_name",
	"payer_email",
	"order_id",
	"currency",
)
stripe_settings = frappe.get_doc("Stripe Settings","Stripe")
stripe.api_key = stripe_settings.get_password(fieldname="secret_key", raise_exception=False)

def get_context(context):
	context.no_cache = 1

	# all these keys exist in form_dict
	if not (set(expected_keys) - set(list(frappe.form_dict))):
		for key in expected_keys:
			context[key] = frappe.form_dict[key]

		gateway_controller = get_gateway_controller(context.reference_doctype, context.reference_docname)
		context.publishable_key = get_api_key(context.reference_docname, gateway_controller)
		context.image = get_header_image(context.reference_docname, gateway_controller)

		context["amount"] = fmt_money(amount=context["amount"], currency=context["currency"])

		if is_a_subscription(context.reference_doctype, context.reference_docname):
			payment_plan = frappe.db.get_value(
				context.reference_doctype, context.reference_docname, "payment_plan"
			)
			recurrence = frappe.db.get_value("Payment Plan", payment_plan, "recurrence")

			context["amount"] = context["amount"] + " " + _(recurrence)

	else:
		frappe.redirect_to_message(
			_("Some information is missing"),
			_("Looks like someone sent you to an incomplete URL. Please ask them to look into it."),
		)
		frappe.local.flags.redirect_location = frappe.local.response.location
		raise frappe.Redirect


def get_api_key(doc, gateway_controller):
	publishable_key = frappe.db.get_value("Stripe Settings", gateway_controller, "publishable_key")
	if cint(frappe.form_dict.get("use_sandbox")):
		publishable_key = frappe.conf.sandbox_publishable_key

	return publishable_key


def get_header_image(doc, gateway_controller):
	header_image = frappe.db.get_value("Stripe Settings", gateway_controller, "header_img")

	return header_image


@frappe.whitelist(allow_guest=True)
def make_payment(stripe_token_id, data,reference_doctype=None, reference_docname=None):
	data = json.loads(data)

	data.update({"stripe_token_id": stripe_token_id})

	gateway_controller = get_gateway_controller(reference_doctype, reference_docname)

	if is_a_subscription(reference_doctype, reference_docname):
		reference = frappe.get_doc(reference_doctype, reference_docname)
		data = reference.create_subscription("stripe", gateway_controller, data)
	else:
		data = frappe.get_doc("Stripe Settings", gateway_controller).create_request(data)

	frappe.db.commit()
	return data


def is_a_subscription(reference_doctype, reference_docname):
	if not frappe.get_meta(reference_doctype).has_field("is_a_subscription"):
		return False
	return frappe.db.get_value(reference_doctype, reference_docname, "is_a_subscription")


@frappe.whitelist(allow_guest=True)
def save_card(email_id,payment_method_id):
	lead_doc = frappe.get_doc("Lead", {"email_id": email_id})
	customer_id=lead_doc.custom_customer_stripe_id
	lead_doc.custom_stripe_token = payment_method_id
	lead_doc.save()

	payment_method = stripe.PaymentMethod.attach(
        payment_method_id,
        customer=customer_id,
    )


	stripe.Customer.modify(
        customer_id,
        invoice_settings={
            'default_payment_method': payment_method_id,
        }
    )


@frappe.whitelist()
def process_payment_with_saved_card(payment_method_id, email_id, amount):
    try:
        # Print to check if the function is called
        print("process_payment_with_saved_card function called",amount*100)

        # Retrieve the customer ID and details based on the email_id
        lead_doc = frappe.get_doc("Lead", {"email_id": email_id})
        customer_id = lead_doc.custom_customer_stripe_id
        customer_name = lead_doc.first_name  # Assuming the name is stored in 'lead_name'
        customer_address = {
            "line1": "Second Floor, F-468, Phase 8B, Industrial Area, Mohali Village, Sahibzada Ajit Singh Nagar, Punjab 140307",
            "city": "Sahibzada Ajit Singh Nagar",
            "state": "Punjab",
            "postal_code": "140307",
            "country": "IN"
        }


        # Print to check if customer_id and other details are retrieved
        print(f"Customer ID retrieved: {customer_id}")
        print(f"Customer Name: {customer_name}")
        print(f"Customer Address: {customer_address}")

        if not customer_id:
            frappe.throw("Customer not found.")

        # Create a PaymentIntent with the saved card, including description, name, and address
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency='inr',
            customer=customer_id,
            payment_method=payment_method_id,
            off_session=True,
            confirm=True,
            description="Payment for order #XYZ123",  # Include a relevant description
            shipping={
                "name": customer_name,
                "address": customer_address
            }
        )

        # Print to check if PaymentIntent is created
        print(f"PaymentIntent created: {payment_intent}")

        return {"status": "success", "payment_intent": payment_intent}
    except stripe.error.CardError as e:
        print(f"Stripe CardError: {e.error.message}")
        frappe.throw(f"Payment failed: {e.error.message}")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        frappe.throw(f"An error occurred: {str(e)}")

@frappe.whitelist(allow_guest=True)
def get_saved_card(email_id):
	try:
		lead_doc = frappe.get_doc("Lead", {"email_id": email_id})
		customer_id=lead_doc.custom_customer_stripe_id
		payment_methods = stripe.PaymentMethod.list(
            customer=customer_id,
            type="card",
        )
		print("saved card data===============================",payment_methods.data)
		return payment_methods.data
	except Exception as e:
		print(f"Error retrieving saved cards: {e}")
		