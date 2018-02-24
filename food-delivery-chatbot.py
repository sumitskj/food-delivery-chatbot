
import json
import datetime
import time
import os
import dateutil.parser
import logging
import boto3

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)


        

# --- Helper fuctions from aws lex documentation ---


def elicit_slot(session_attributes, intent_name, slots, slot_to_elicit, message,response_card):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ElicitSlot',
            'intentName': intent_name,
            'slots': slots,
            'slotToElicit': slot_to_elicit,
            'message': message,
            'responseCard': response_card
        }
    }


def confirm_intent(session_attributes, intent_name, slots, message, response_card):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'ConfirmIntent',
            'intentName': intent_name,
            'slots': slots,
            'message': message,
            'responseCard': response_card
        }
    }


def close(session_attributes, fulfillment_state, message):
    response = {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': fulfillment_state,
            'message': message
        }
    }

    return response


def delegate(session_attributes, slots):
    return {
        'sessionAttributes': session_attributes,
        'dialogAction': {
            'type': 'Delegate',
            'slots': slots
        }
    }

def build_response_card(title, options):
    """
    Build a responseCard with a title, subtitle, and an optional set of options which should be displayed as buttons.
    """
    buttons = None
    if options is not None:
        buttons = []
        for i in range(min(5, len(options))):
            buttons.append(options[i])

    return {
        'contentType': 'application/vnd.amazonaws.card.generic',
        'version': 1,
        'genericAttachments': [{
            'title': title,
        
            'buttons': buttons
        }]
    }
# --- My functions ---


def safe_int(n):
    
    if n is not None:
        return int(n)
    return n


def try_ex(func):
     try:
        return func()
     except KeyError:
        return None




def isvalid_snack(snacks_type):
    snacks = ['burger','franky','pizza','samosa','fries','sandwich']
    return snacks_type.lower() in snacks


def isvalid_city(city):
    valid_cities = ['new york', 'los angeles', 'chicago', 'houston', 'philadelphia', 'phoenix', 'san antonio',
                    'san diego', 'dallas', 'san jose', 'austin', 'jacksonville', 'san francisco', 'indianapolis',
                    'columbus', 'fort worth', 'charlotte', 'detroit', 'el paso', 'seattle', 'denver', 'washington dc',
                    'memphis', 'boston', 'nashville', 'baltimore', 'portland']
    return city.lower() in valid_cities


def isvalid_beverage(drink_type):
    beverages = ['beer','thumps_up','coca-cola','pepsi','frooti','appy']
    return drink_type.lower() in beverages




def build_validation_result(isvalid, violated_slot, message_content):
    return {
        'isValid': isvalid,
        'violatedSlot': violated_slot,
        'message': {'contentType': 'PlainText', 'content': message_content}
    }


def validate_beverage(slots):
    location = try_ex(lambda: slots['Location'])
    drink = try_ex(lambda: slots['drink'])
    
    quantity = safe_int(try_ex(lambda: slots['amount']))
    

    if location and not isvalid_city(location):
        return build_validation_result(
            False,
            'Location',
            'We currently do not support {} as a valid delivery address.  Can you try a different city?'.format(location)
        )

    
    if quantity is not None and quantity < 1:
        return build_validation_result(
            False,
            'amount',
            'Sorry, you can order one or more than one beverage. Please , can you tell how many beverages do you want?'
        )

    if drink and not isvalid_beverage(drink):
        return build_validation_result(
            False,
            'drink',
            'I did not recognize that beverage.  What type of beverage do you want to order?  '
            'Popular beverages are coca-cola, pepsi, beer')

    return {'isValid': True}


def validate_snacks(slots):
    location = try_ex(lambda: slots['address'])
    snack = try_ex(lambda: slots['Fast'])
    quantity = safe_int(try_ex(lambda: slots['number']))
    

    if location and not isvalid_city(location):
        return build_validation_result(
            False,
            'address',
            'We currently do not support {} as a valid delivery address.  Can you try a different city?'.format(location)
        )

   
    if quantity is not None and (quantity < 1 ):
        return build_validation_result(
            False,
            'number',
            'Sorry, you have to order one or more than one Fast food. So how many quantity of your order do you want us to bring ?'
        )

    if snack and not isvalid_snack(snack):
        return build_validation_result(False, 'Fast', 'I did not recognize that Fast food.  Do you want to have pizza, fries ,burger?')

    return {'isValid': True}



def build_options(slot, snacks):
    """
    Build a list of potential options for a given slot, to be used in responseCard generation.
    """
    
    if slot == 'Fast':
        return [
            {'text': 'Pizza', 'value': 'Pizza'},
            {'text': 'Fries', 'value': 'Fries'},
            {'text': 'Franky', 'value': 'Franky'},
            {'text': 'Burger', 'value': 'Burger'},
            {'text': 'Sandwich', 'value': 'Sandwich'},
            {'text': 'Samosa', 'value': 'Samosa'}
           
        ]
    elif slot == 'drink':
        return [
            {'text': 'Coca-Cola', 'value': 'Coca-cola'},
            {'text': 'Appy', 'value': 'Appy'},
            {'text': 'Thumps_up', 'value': 'Thumps-Up'},
            {'text': 'Beer', 'value': 'Beer'},
            {'text': 'Frooti', 'value': 'Frooti'},
            {'text': 'Pepsi', 'value': 'Pepsi'}
            
        ]
    
        
        


    
def order_snacks(intent_request):
   
    dynamo = boto3.resource('dynamodb')
    table = dynamo.Table('snack_orders')
    
    location = try_ex(lambda: intent_request['currentIntent']['slots']['address'])
    snacks = try_ex(lambda: intent_request['currentIntent']['slots']['Fast'])
    quantity = safe_int(try_ex(lambda: intent_request['currentIntent']['slots']['number']))
    uid = try_ex(lambda: intent_request['userId'])
    
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}

    # Load confirmation history and track the current reservation.
    reservation = json.dumps({
        'ReservationType': 'Snacks',
        'address': location,
        'number': quantity,
        'Fast': snacks
    })

    session_attributes['currentReservation'] = reservation

    if intent_request['invocationSource'] == 'DialogCodeHook':
        # Validate any slots which have been specified.  If any are invalid, re-elicit for their value
        validation_result = validate_snacks(intent_request['currentIntent']['slots'])
        if not validation_result['isValid']:
            slots = intent_request['currentIntent']['slots']
            slots[validation_result['violatedSlot']] = None

            return elicit_slot(
                session_attributes,
                intent_request['currentIntent']['name'],
                slots,
                validation_result['violatedSlot'],
                validation_result['message'],
                build_response_card(
                    'Specify {}'.format(validation_result['violatedSlot']),
                    build_options(validation_result['violatedSlot'], snacks)
                    
                )
            )

        # Otherwise, let native DM rules determine how to elicit for slots and prompt for confirmation.  Pass price
        # back in sessionAttributes once it can be calculated; otherwise clear any setting from sessionAttributes.
     
        if location and quantity and snacks :
            
            price = quantity*11
            session_attributes['currentReservationPrice'] = price
        else:
            try_ex(lambda: session_attributes.pop('currentReservationPrice'))

        session_attributes['currentReservation'] = reservation
        return delegate(session_attributes, intent_request['currentIntent']['slots'])

    
    logger.debug('orderSnacks under={}'.format(reservation))

    try_ex(lambda: session_attributes.pop('currentReservationPrice'))
    try_ex(lambda: session_attributes.pop('currentReservation'))
    session_attributes['lastConfirmedReservation'] = reservation
    DynamoDict = {
        'uid': uid,
        'snack': snacks, 
        'quantity': quantity, 
        'address': location,
        'price': quantity*11
        
        }

    table.put_item(Item=DynamoDict)
    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'Thanks, I have placed your order and your order ID is {}. It will be delivered before 30 minutes. Please let me know if you would like to order some Beverages '.format(
                intent_request['userId']
                )
                      
        }
    )

def order_help(intent_request):
    session_attributes=None
    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'Our services allows you to order Fast Foods and Beverages \n Beverages are: \n 1.Coca-cola \n 2.Appy \n3.Thumps-up\n4.Beer\n5.Frooti\n6.Pepsi\nFast foods are :\n1.Pizza\n2.Fries\n3.Franky\n4.Burger\n5.Sandwich\n6.Samosa'
      
        }
    )
def order_beverages(intent_request):
    dynamo = boto3.resource('dynamodb')
    table = dynamo.Table('drink_orders')
    slots = intent_request['currentIntent']['slots']
    drink = slots['drink']
    quantity = slots['amount']
    location = slots['Location']
    uid= intent_request['userId']
    
    confirmation_status = intent_request['currentIntent']['confirmationStatus']
    session_attributes = intent_request['sessionAttributes'] if intent_request['sessionAttributes'] is not None else {}
    last_confirmed_reservation = try_ex(lambda: session_attributes['lastConfirmedReservation'])
    
    if last_confirmed_reservation:
        last_confirmed_reservation = json.loads(last_confirmed_reservation)
    confirmation_context = try_ex(lambda: session_attributes['confirmationContext'])

    # Load confirmation history and track the current reservation.
    reservation = json.dumps({
        'ReservationType': 'Drinks',
        'Location': location,
        'amount': quantity,
        'drink': drink
    })
    session_attributes['currentReservation'] = reservation
    price=0
    if location and quantity and drink:
        
        price = 10
        session_attributes['currentReservationPrice'] = price

    if intent_request['invocationSource'] == 'DialogCodeHook':
        # Validate any slots which have been specified.  If any are invalid, re-elicit for their value
        validation_result = validate_beverage(intent_request['currentIntent']['slots'])
        if not validation_result['isValid']:
            slots[validation_result['violatedSlot']] = None
            return elicit_slot(
                session_attributes,
                intent_request['currentIntent']['name'],
                slots,
                validation_result['violatedSlot'],
                validation_result['message'],
                build_response_card(
                    'Specify {}'.format(validation_result['violatedSlot']),
                    
                    build_options(validation_result['violatedSlot'], drink)
                )
            )

        # Determine if the intent (and current slot settings) has been denied.  The messaging will be different
        # if the user is denying a reservation he initiated or an auto-populated suggestion.
        if confirmation_status == 'Denied':
            # Clear out auto-population flag for subsequent turns.
            try_ex(lambda: session_attributes.pop('confirmationContext'))
            try_ex(lambda: session_attributes.pop('currentReservation'))
            if confirmation_context == 'AutoPopulate':
                return elicit_slot(
                    session_attributes,
                    intent_request['currentIntent']['name'],
                    {
                        'Location':None,
                        'amount': None,
                        'drink': None
                    },
                    'Location',
                    {
                        'contentType': 'PlainText',
                        'content': 'What beverages do you want to order? We have'
                    },
                    build_response_card(
                    'Specify beverage',
                    
                    build_options('drink', drink)
                    )
                    
                )

            return delegate(session_attributes, intent_request['currentIntent']['slots'])

        if confirmation_status == 'None':
            # If we are currently auto-populating but have not gotten confirmation, keep requesting for confirmation.
            if (not location and not quantity and not drink)\
                    or confirmation_context == 'AutoPopulate':
                if last_confirmed_reservation and try_ex(lambda: last_confirmed_reservation['ReservationType']) == 'Snacks':
                    # If the user's previous reservation was a hotel - prompt for a rental with
                    # auto-populated values to match this reservation.
                    session_attributes['confirmationContext'] = 'AutoPopulate'
                    return confirm_intent(
                        session_attributes,
                        intent_request['currentIntent']['name'],
                        {
                            'Location': last_confirmed_reservation['address'],
                            
                            'drink': None,
                            'amount': None
                        },
                        {
                            'contentType': 'PlainText',
                            'content': 'Is this beverage order is with your {} {} Fast food order at{} ?'.format(
                                last_confirmed_reservation['number'],
                                last_confirmed_reservation['Fast'],
                                last_confirmed_reservation['address']
                            )
                        },
                        build_response_card(
                        'Related',
                        
                        [{'text': 'Yes', 'value': 'Yes'}, {'text': 'No', 'value': 'No'}]
                        )
                        
                        
                    )

            # Otherwise, let native DM rules determine how to elicit for slots and/or drive confirmation.
            return delegate(session_attributes, intent_request['currentIntent']['slots'])

        # If confirmation has occurred, continue filling any unfilled slot values or pass to fulfillment.
        if confirmation_status == 'Confirmed':
            # Remove confirmationContext from sessionAttributes so it does not confuse future requests
            try_ex(lambda: session_attributes.pop('confirmationContext'))
            if confirmation_context == 'AutoPopulate':
                
                if not drink:
                    return elicit_slot(
                        session_attributes,
                        intent_request['currentIntent']['name'],
                        intent_request['currentIntent']['slots'],
                        'drink',
                        {
                            'contentType': 'PlainText',
                            'content': 'What type of beverage would you like to order? We have: '
                                       
                        },
                        build_response_card(
                        'Specify beverage',
                        
                        build_options('drink', drink)
                        )
                       
                    )

            return delegate(session_attributes, intent_request['currentIntent']['slots'])

   
    logger.debug('orderBeverage at={}'.format(reservation))
    del session_attributes['currentReservationPrice']
    del session_attributes['currentReservation']
    session_attributes['lastConfirmedReservation'] = reservation
    
    DynamoDict = {
        'uid': uid,
        'drink': drink, 
        'quantity': quantity, 
        'location': location,
        'price': price
        
        }

    table.put_item(Item=DynamoDict)
    return close(
        session_attributes,
        'Fulfilled',
        {
            'contentType': 'PlainText',
            'content': 'Thanks, I have placed your order and your order ID is {}. It will be delivered before 30 minutes.'.format(
                intent_request['userId']
                )
        }
    )


# --- Intents ---


def dispatch(intent_request):
    """
    Called when the user specifies an intent for this bot.
    """

    logger.debug('dispatch userId={}, intentName={}'.format(intent_request['userId'], intent_request['currentIntent']['name']))

    intent_name = intent_request['currentIntent']['name']

    # Dispatch to your bot's intent handlers
    if intent_name == 'Help':
        return order_help(intent_request)
    elif intent_name == 'FastFood':
        return order_snacks(intent_request)
    elif intent_name == 'Beverages':
        return order_beverages(intent_request)

    raise Exception('Intent with name ' + intent_name + ' not supported')


# --- Main handler ---


def lambda_handler(event, context):
    """
    Route the incoming request based on intent.
    The JSON body of the request is provided in the event slot.
    """
    # By default, treat the user request as coming from the America/New_York time zone.
    
    os.environ['TZ'] = 'America/New_York'
    time.tzset()
    logger.debug('event.bot.name={}'.format(event['bot']['name']))
    intent_name = event['currentIntent']['name']
       
    return dispatch(event)

