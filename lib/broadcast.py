#! /usr/bin/python3

"""
Broadcast a message, with or without a price.

Multiple messages per block are allowed. Bets are be made on the 'timestamp'
field, and not the block index.

An address is a feed of broadcasts. Feeds may be locked with a broadcast whose
text field is identical to ‘lock’ (case insensitive). Bets on a feed reference
the address that is the source of the feed in an output which includes the
(latest) required fee.

Broadcasts without a price may not be used for betting. Broadcasts about events
with a small number of possible outcomes (e.g. sports games), should be
written, for example, such that a price of 1 XCP means one outcome, 2 XCP means
another, etc., which schema should be described in the 'text' field.

fee_fraction: .05 XCP means 5%. It may be greater than 1, however; but
because it is stored as a four‐byte integer, it may not be greater than about
42.
"""

import struct
import decimal
D = decimal.Decimal
import logging

from . import (util, exceptions, config, bitcoin)

FORMAT = '>IdI52p'
LENGTH = 4 + 8 + 4 + 52
ID = 30


def validate (db, source, timestamp, value, fee_fraction_int, text):
    problems = []

    if fee_fraction_int > 4294967295:
        problems.append('fee fraction greater than 42.94967295')

    if not source:
        problems.append('null source address')
    # Check previous broadcast in this feed.
    broadcasts = util.get_broadcasts(db, validity='valid', source=source, order_by='tx_index', order_dir='asc')
    if broadcasts:
        last_broadcast = broadcasts[-1]
        if last_broadcast['locked']:
            problems.append('locked feed')
        elif timestamp <= last_broadcast['timestamp']:
            problems.append('feed timestamps not monotonically increasing')

    return problems

def compose (db, source, timestamp, value, fee_fraction, text):

    # Store the fee fraction as an integer.
    fee_fraction_int = int(D(fee_fraction) * D(1e8))

    problems = validate(db, source, timestamp, value, fee_fraction_int, text)
    if problems: raise exceptions.BroadcastError(problems)

    data = config.PREFIX + struct.pack(config.TXTYPE_FORMAT, ID)
    data += struct.pack(FORMAT, timestamp, value, fee_fraction_int,
                        text.encode('utf-8'))
    if len(data) > 80:
        raise exceptions.BroadcastError('Text is greater than 52 bytes.')
    return (source, None, None, config.MIN_FEE, data)

def parse (db, tx, message):
    broadcast_parse_cursor = db.cursor()

    # Unpack message.
    try:
        assert len(message) == LENGTH
        timestamp, value, fee_fraction_int, text = struct.unpack(FORMAT, message)
        text = text.decode('utf-8')
        validity = 'valid'
    except struct.error as e:
        timestamp, value, fee_fraction_int, text = None, None, None, None
        validity = 'invalid: could not unpack'

    if validity == 'valid':
        # For SQLite3
        timestamp = min(timestamp, config.MAX_INT)
        value = min(value, config.MAX_INT)

        problems = validate(db, tx['source'], timestamp, value, fee_fraction_int, text)
        if problems: validity = 'invalid: ' + ';'.join(problems)

    # Lock?
    lock = False
    if text and text.lower() == 'lock':
        lock = True
        timestamp, value, fee_fraction_int, text = None, None, None, None
    else:
        lock = False

    # Add parsed transaction to message-type–specific table.
    bindings = {
        'tx_index': tx['tx_index'],
        'tx_hash': tx['tx_hash'],
        'block_index': tx['block_index'],
        'source': tx['source'],
        'timestamp': timestamp,
        'value': value,
        'fee_fraction_int': fee_fraction_int,
        'text': text,
        'locked': lock,
        'validity': validity,
    }
    sql='insert into broadcasts values(:tx_index, :tx_hash, :block_index, :source, :timestamp, :value, :fee_fraction_int, :text, :locked, :validity)'
    broadcast_parse_cursor.execute(sql, bindings)

    # Negative values are invalid.
    if value < 0 or value == None:
        broadcast_parse_cursor.close()
        return

    # Handle bet matches that use this feed.
    broadcast_parse_cursor.execute('''SELECT * FROM bet_matches \
                                      WHERE (validity=? AND feed_address=?)
                                      ORDER BY tx1_index ASC, tx0_index ASC''',
                                   ('valid', tx['source']))
    for bet_match in broadcast_parse_cursor.fetchall():
        broadcast_bet_match_cursor = db.cursor()
        validity = 'valid'
        bet_match_id = bet_match['tx0_hash'] + bet_match['tx1_hash']

        # Calculate total funds held in escrow and total fee to be paid if
        # the bet match is settled.
        total_escrow = bet_match['forward_amount'] + bet_match['backward_amount']
        fee_fraction = D(bet_match['fee_fraction_int']) / D(1e8)
        fee = round(total_escrow * fee_fraction)

        # Get known bet match type IDs.
        cfd_type_id = util.BET_TYPE_ID['BullCFD'] + util.BET_TYPE_ID['BearCFD']
        equal_type_id = util.BET_TYPE_ID['Equal'] + util.BET_TYPE_ID['NotEqual']

        # Get the bet match type ID of this bet match.
        bet_match_type_id = bet_match['tx0_bet_type'] + bet_match['tx1_bet_type']

        # Contract for difference, with determinate settlement date.
        if validity == 'valid' and bet_match_type_id == cfd_type_id:

            # Recognise tx0, tx1 as the bull, bear (in the right direction).
            if bet_match['tx0_bet_type'] < bet_match['tx1_bet_type']:
                bull_address = bet_match['tx0_address']
                bear_address = bet_match['tx1_address']
                bull_escrow = bet_match['forward_amount']
                bear_escrow = bet_match['backward_amount']
            else:
                bull_address = bet_match['tx1_address']
                bear_address = bet_match['tx0_address']
                bull_escrow = bet_match['backward_amount']
                bear_escrow = bet_match['forward_amount']

            leverage = D(bet_match['leverage']) / 5040
            initial_value = bet_match['initial_value']

            bear_credit = D(bear_escrow) - (D(value) - D(initial_value)) * D(leverage) * D(config.UNIT)
            bull_credit = D(total_escrow) - bear_credit
            bear_credit = round(bear_credit)
            bull_credit = round(bull_credit)

            if bet_match['validity'] == 'valid':
                # Liquidate, as necessary.
                if bull_credit >= total_escrow:
                    bull_credit = total_escrow
                    bear_credit = 0
                    util.credit(db, tx['block_index'], bull_address, 'XCP', bull_credit)
                    validity = 'Force‐Liquidated Bear'
                elif bull_credit <= 0:
                    bull_credit = 0
                    bear_credit = total_escrow
                    util.credit(db, tx['block_index'], bear_address, 'XCP', bear_credit)
                    validity = 'Force‐Liquidated Bull'

                if validity.startswith('Force‐Liquidated'):
                    # Pay fee to feed.
                    util.credit(db, tx['block_index'], bet_match['feed_address'], 'XCP', fee)

                    logging.info('Contract Force‐Liquidated: {} XCP credited to the bull, {} XCP credited to the bear, and {} XCP credited to the feed address ({})'.format(util.devise(db, bull_credit, 'XCP', 'output'), util.devise(db, bear_credit, 'XCP', 'output'), util.devise(db, fee, 'XCP', 'output'), bet_match_id))

            # Settle.
            if validity == 'valid' and timestamp >= bet_match['deadline']:
                util.credit(db, tx['block_index'], bull_address, 'XCP', bull_credit)
                util.credit(db, tx['block_index'], bear_address, 'XCP', bear_credit)

                # Pay fee to feed.
                util.credit(db, tx['block_index'], bet_match['feed_address'], 'XCP', fee)

                validity = 'Settled (CFD)'
                logging.info('Contract Settled: {} XCP credited to the bull, {} XCP credited to the bear, and {} XCP credited to the feed address ({})'.format(util.devise(db, bull_credit, 'XCP', 'output'), util.devise(db, bear_credit, 'XCP', 'output'), util.devise(db, fee, 'XCP', 'output'), bet_match_id))

        # Equal[/NotEqual] bet.
        if validity == 'valid' and  bet_match_type_id == equal_type_id and timestamp >= bet_match['deadline']:

            # Recognise tx0, tx1 as the bull, bear (in the right direction).
            if bet_match['tx0_bet_type'] < bet_match['tx1_bet_type']:
                equal_address = bet_match['tx0_address']
                notequal_address = bet_match['tx1_address']
            else:
                equal_address = bet_match['tx1_address']
                notequal_address = bet_match['tx0_address']

            # Decide who won, and credit appropriately.
            if value == bet_match['target_value']:
                winner = 'Equal'
                util.credit(db, tx['block_index'], equal_address, 'XCP', total_escrow)
                validity = 'Settled for Equal'
            else:
                winner = 'NotEqual'
                util.credit(db, tx['block_index'], notequal_address, 'XCP', total_escrow)
                validity = 'Settled for NotEqual'

            # Pay fee to feed.
            util.credit(db, tx['block_index'], bet_match['feed_address'], 'XCP', fee)

            logging.info('Contract Settled: {} won the pot of {} XCP; {} XCP credited to the feed address ({})'.format(winner, util.devise(db, total_escrow, 'XCP', 'output'), util.devise(db, fee, 'XCP', 'output'), bet_match_id))

        # Update the bet match's status.
        bindings = {
            'validity': validity,
            'bet_match_id': bet_match['tx0_hash'] + bet_match['tx1_hash']
        }
        sql='update bet_matches set validity = :validity where id = :bet_match_id'
        broadcast_parse_cursor.execute(sql, bindings)

        broadcast_bet_match_cursor.close()

    broadcast_parse_cursor.close()

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
