var stripe = Stripe("{{ publishable_key }}");

var elements = stripe.elements();

var style = {
	base: {
		color: '#32325d',
		lineHeight: '18px',
		fontFamily: '"Helvetica Neue", Helvetica, sans-serif',
		fontSmoothing: 'antialiased',
		fontSize: '16px',
		'::placeholder': {
			color: '#aab7c4'
		}
	},
	invalid: {
		color: '#fa755a',
		iconColor: '#fa755a'
	}
};

var card = elements.create('card', {
	hidePostalCode: true,
	style: style
});



card.mount('#card-element');



function setOutcome(result) {

	if (result.token) {
		$('#submit').prop('disabled', true)
		$('#submit').html(__('Processing...'))

		set_paymentMethod();

		frappe.call({
			method:"payments.templates.pages.stripe_checkout.make_payment",
			freeze:true,
			headers: {"X-Requested-With": "XMLHttpRequest"},
			args: {
				"stripe_token_id": result.token.id,
				"data": JSON.stringify({{ frappe.form_dict|json }}),
				"reference_doctype": "{{ reference_doctype }}",
				"reference_docname": "{{ reference_docname }}",
			},
			callback: function(r) {
				if (r.message.status == "Completed") {
					$('#submit').hide()
					$('.success').show()
					setTimeout(function() {
						window.location.href = r.message.redirect_to
					}, 2000);
				} else {
					$('#submit').hide()
					$('.error').show()
					setTimeout(function() {
						window.location.href = r.message.redirect_to
					}, 2000);
				}
			}
		});

	} else if (result.error) {
		$('.error').html(result.error.message);
		$('.error').show()
	}
}

async function set_paymentMethod(){

	var { paymentMethod, error } = await stripe.createPaymentMethod({
		type: 'card',
		card: card,
	});
	if (error) {
		// Display error.message in your UI
		console.error(error.message);
	} else {
		// paymentMethod.id is the payment method ID
		var paymentMethodId = paymentMethod.id;
	}

	frappe.call({
		method:"payments.templates.pages.stripe_checkout.save_card",
		freeze:true,
		headers: {"X-Requested-With": "XMLHttpRequest"},
		args: {
			"email_id":$('input[name=cardholder-email]').val(),
			"payment_method_id":paymentMethodId
		},
	})

	
}


function get_saved_cards(){
	
	frappe.call({
		method:"payments.templates.pages.stripe_checkout.get_saved_card",
		freeze:true,
		headers: {"X-Requested-With": "XMLHttpRequest"},
		args: {
			"email_id":$('input[name=cardholder-email]').val(),
		},    
		callback: function(response) {
			if (response.message) {
				displaySavedCards(response.message);
			} else {
				frappe.msgprint('No saved cards found.');
			}
		}
	});

}

function displaySavedCards(cards) {
	const $select = $('#saved-cards');
	$select.empty();  // Clear any existing options

	console.log("Card ================================================",cards)

	cards.forEach(function(card) {
		const optionText = `${card.card.brand} XXXX ${card.card.last4} (Exp: ${card.card.exp_month}/${card.card.exp_year})`;
		const optionValue = card.id;

		// Append new option to the select element
		$select.append(new Option(optionText, optionValue));
	});
}



card.on('change', function(event) {
	var displayError = document.getElementById('card-errors');
	if (event.error) {
		displayError.textContent = event.error.message;
	} else {
		displayError.textContent = '';
	}
});

frappe.ready(function() {
	get_saved_cards();
	
	
	$('#pay-with-saved-card').click(function() {
		const selectedCardId = $('#saved-cards').val();
		console.log("call hone wala hai ")
        if (selectedCardId) {
            // Call the backend to process the payment with the selected card
			console.log("call hogya")
            frappe.call({
                method: "payments.templates.pages.stripe_checkout.process_payment_with_saved_card",
                freeze: true,
                headers: {"X-Requested-With": "XMLHttpRequest"},
				args: {
					"payment_method_id": selectedCardId,
					"email_id": $('input[name=cardholder-email]').val(),
					"amount": 100*100 // Amount in cents, e.g., $10.00
				},
                callback: function(response) {
                    if (response.message) {
                        frappe.msgprint('Payment successful!');
                        // Redirect to a success page or show a confirmation message
                    } else {
                        frappe.msgprint('Payment failed. Please try again.');
                    }
                },
                error: function(xhr, status, error) {
                    console.error('Error processing payment:', error);
                    frappe.msgprint('Payment failed due to an error.');
                },
                complete: function() {
                    frappe.unfreeze();  // Unfreeze the UI after the request is complete
                }
            });
        } else {
            frappe.msgprint('Please select a saved card.');
        }
    });

	
	$('#submit').off("click").on("click", function(e) {
		e.preventDefault();
		var extraDetails = {
			name: $('input[name=cardholder-name]').val(),
			email: $('input[name=cardholder-email]').val(),
			address_line1: "Second Floor, F-468, Phase 8B, Industrial Area, Mohali Village, Sahibzada Ajit Singh Nagar, Punjab 140307",
			address_city: "Sahibzada Ajit Singh Nagar",
			address_state: "Punjab",
			address_zip: "140307",
			address_country: "IN"
		}
		stripe.createToken(card, extraDetails).then(setOutcome);
	})
});
