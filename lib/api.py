#! /usr/bin/python3

import sys
import os
import threading
import decimal
import time
import json
import logging
from logging import handlers as logging_handlers
D = decimal.Decimal

import apsw
import cherrypy
from cherrypy import wsgiserver
from jsonrpc import JSONRPCResponseManager, dispatcher

from . import (config, bitcoin, exceptions, util, bitcoin)
from . import (send, order, btcpay, issuance, broadcast, bet, dividend, burn, cancel)

class APIServer(threading.Thread):

    def __init__ (self):
        threading.Thread.__init__(self)

    def run (self):
        db = util.connect_to_db(flags='SQLITE_OPEN_READONLY')

        ######################
        #READ API
        # TODO: Move all of these functions from util.py here (and use native SQLite queries internally).

        @dispatcher.add_method
        def get_address(address, start_block=None, end_block=None):
            try:
                return util.get_address(db, address=address, start_block=start_block, end_block=end_block)
            except exceptions.InvalidAddressError:
                return None

        @dispatcher.add_method
        def get_balances(filters=None, order_by=None, order_dir=None, filterop="and"):
            return util.get_balances(db,
                filters=filters,
                order_by=order_by,
                order_dir=order_dir,
                filterop=filterop)

        @dispatcher.add_method
        def get_bets(filters=None, is_valid=True, order_by=None, order_dir=None, start_block=None, end_block=None, filterop="and"):
            return util.get_bets(db,
                filters=filters,
                validity='valid' if bool(is_valid) else None,
                order_by=order_by,
                order_dir=order_dir,
                start_block=start_block,
                end_block=end_block,
                filterop=filterop)

        @dispatcher.add_method
        def get_bet_matches(filters=None, is_valid=True, order_by=None, order_dir=None, start_block=None, end_block=None, filterop="and"):
            return util.get_bet_matches(db,
                filters=filters,
                validity='valid' if bool(is_valid) else None,
                order_by=order_by,
                order_dir=order_dir,
                start_block=start_block,
                end_block=end_block,
                filterop=filterop)

        @dispatcher.add_method
        def get_broadcasts(filters=None, is_valid=True, order_by=None, order_dir=None, start_block=None, end_block=None, filterop="and"):
            return util.get_broadcasts(db,
                filters=filters,
                validity='valid' if bool(is_valid) else None,
                order_by=order_by,
                order_dir=order_dir,
                start_block=start_block,
                end_block=end_block,
                filterop=filterop)

        @dispatcher.add_method
        def get_btcpays(filters=None, is_valid=True, order_by=None, order_dir=None, start_block=None, end_block=None, filterop="and"):
            return util.get_btcpays(db,
                filters=filters,
                validity='valid' if bool(is_valid) else None,
                order_by=order_by,
                order_dir=order_dir,
                start_block=start_block,
                end_block=end_block,
                filterop=filterop)

        @dispatcher.add_method
        def get_burns(filters=None, is_valid=True, order_by=None, order_dir=None, start_block=None, end_block=None, filterop="and"):
            return util.get_burns(db,
                filters=filters,
                validity='valid' if bool(is_valid) else None,
                order_by=order_by,
                order_dir=order_dir,
                start_block=start_block,
                end_block=end_block,
                filterop=filterop)

        @dispatcher.add_method
        def get_cancels(filters=None, is_valid=True, order_by=None, order_dir=None, start_block=None, end_block=None, filterop="and"):
            return util.get_cancels(db,
                filters=filters,
                validity='valid' if bool(is_valid) else None,
                order_by=order_by,
                order_dir=order_dir,
                start_block=start_block,
                end_block=end_block,
                filterop=filterop)

        @dispatcher.add_method
        def get_credits (filters=None, order_by=None, order_dir=None, filterop="and"):
            return util.get_credits(db,
                filters=filters,
                order_by=order_by,
                order_dir=order_dir,
                filterop=filterop)

        @dispatcher.add_method
        def get_debits (filters=None, order_by=None, order_dir=None, filterop="and"):
            return util.get_debits(db,
                filters=filters,
                order_by=order_by,
                order_dir=order_dir,
                filterop=filterop)

        @dispatcher.add_method
        def get_dividends(filters=None, is_valid=True, order_by=None, order_dir=None, start_block=None, end_block=None, filterop="and"):
            return util.get_dividends(db,
                filters=filters,
                validity='valid' if bool(is_valid) else None,
                order_by=order_by,
                order_dir=order_dir,
                start_block=start_block,
                end_block=end_block,
                filterop=filterop)

        @dispatcher.add_method
        def get_issuances(filters=None, is_valid=True, order_by=None, order_dir=None, start_block=None, end_block=None, filterop="and"):
            return util.get_issuances(db,
                filters=filters,
                validity='valid' if bool(is_valid) else None,
                order_by=order_by,
                order_dir=order_dir,
                start_block=start_block,
                end_block=end_block,
                filterop=filterop)

        @dispatcher.add_method
        def get_orders (filters=None, is_valid=True, show_expired=True, order_by=None, order_dir=None, start_block=None, end_block=None, filterop="and"):
            return util.get_orders(db,
                filters=filters,
                validity='valid' if bool(is_valid) else None,
                show_expired=show_expired,
                order_by=order_by,
                order_dir=order_dir,
                start_block=start_block,
                end_block=end_block,
                filterop=filterop)

        @dispatcher.add_method
        def get_order_matches (filters=None, is_valid=True, is_mine=False, order_by=None, order_dir=None, start_block=None, end_block=None, filterop="and"):
            return util.get_order_matches(db,
                filters=filters,
                validity='valid' if bool(is_valid) else None,
                is_mine=is_mine,
                order_by=order_by,
                order_dir=order_dir,
                start_block=start_block,
                end_block=end_block,
                filterop=filterop)

        @dispatcher.add_method
        def get_sends (filters=None, is_valid=True, order_by=None, order_dir=None, start_block=None, end_block=None, filterop="and"):
            return util.get_sends(db,
                filters=filters,
                validity='valid' if bool(is_valid) else None,
                order_by=order_by,
                order_dir=order_dir,
                start_block=start_block,
                end_block=end_block,
                filterop=filterop)

        @dispatcher.add_method
        def get_messages(block_index):
            cursor = db.cursor()
            cursor.execute('select * from messages where block_index = ? order by message_index asc', (block_index,))
            messages = cursor.fetchall()
            cursor.close()
            return messages

        @dispatcher.add_method
        def xcp_supply():
            return util.xcp_supply(db)

        @dispatcher.add_method
        def get_asset_info(asset):
            if asset in ['BTC', 'XCP']:
                return {
                    'owner': None,
                    'divisible': True,
                    'locked': False,
                    'total_issued': util.xcp_supply(db) if asset == 'XCP' else None,
                    'callable': False,
                    'call_date': None,
                    'call_price': None,
                    'description': '',
                    'issuer': None
                }
            
            #gets some useful info for the given asset
            issuances = util.get_issuances(db,
                filters={'field': 'asset', 'op': '==', 'value': asset},
                validity='valid',
                order_by='block_index',
                order_dir='asc')
            if not issuances: return None #asset not found, most likely
            else: last_issuance = issuances[-1]

            #get the last issurance message for this asset, which should reflect the current owner and if
            # its divisible (and if it was locked, for that matter)
            locked = not last_issuance['amount'] and not last_issuance['transfer']
            total_issued = sum([e['amount'] for e in issuances])
            return {'owner': last_issuance['issuer'],
                    'divisible': bool(last_issuance['divisible']),
                    'locked': locked,
                    'total_issued': total_issued,
                    'callable': bool(last_issuance['callable']),
                    'call_date': util.isodt(last_issuance['call_date']) if last_issuance['call_date'] else None,
                    'call_price': last_issuance['call_price'],
                    'description': last_issuance['description'],
                    'issuer': last_issuance['issuer']}

        @dispatcher.add_method
        def get_block_info(block_index):
            assert isinstance(block_index, int) 
            cursor = db.cursor()
            cursor.execute('''SELECT * FROM blocks WHERE block_index = ?''', (block_index,))
            try:
                block = cursor.fetchall()[0]
            except IndexError:
                raise exceptions.DatabaseError('No blocks found.')
            cursor.close()
            return block
            
        @dispatcher.add_method
        def get_running_info():
            latestBlockIndex = bitcoin.rpc('getblockcount', [])
            
            try:
                util.database_check(db, latestBlockIndex)
            except:
                caught_up = False
            else:
                caught_up = True

            try:
                last_block = util.last_block(db)
            except:
                last_block = {'block_index': None, 'block_hash': None, 'block_time': None}
                
            return {
                'db_caught_up': caught_up,
                'bitcoin_block_count': latestBlockIndex,
                'last_block': last_block,
                'counterpartyd_version': config.CLIENT_VERSION,
                'running_testnet': config.TESTNET,
                'db_version_major': config.DB_VERSION_MAJOR,
                'db_version_minor': config.DB_VERSION_MINOR,
            }

        @dispatcher.add_method
        def get_asset_names():
            cursor = db.cursor()
            names = [row['asset'] for row in cursor.execute("SELECT DISTINCT asset FROM issuances WHERE validity = 'valid' ORDER BY asset ASC")]
            cursor.close()
            return names

        @dispatcher.add_method
        def get_element_counts():
            counts = {}
            cursor = db.cursor()
            for element in ['transactions', 'blocks', 'debits', 'credits', 'balances', 'sends', 'orders',
                'order_matches', 'btcpays', 'issuances', 'broadcasts', 'bets', 'bet_matches', 'dividends',
                'burns', 'cancels', 'callbacks', 'order_expirations', 'bet_expirations', 'order_match_expirations',
                'bet_match_expirations', 'messages']:
                cursor.execute("SELECT COUNT(*) AS count FROM %s" % element)
                counts[element] = cursor.fetchall()[0]['count']
            cursor.close()
            return counts

        ######################
        #WRITE/ACTION API
        @dispatcher.add_method
        def create_bet(source, feed_address, bet_type, deadline, wager, counterwager, expiration, target_value=0.0, leverage=5040, multisig=config.MULTISIG):
            bet_type_id = util.BET_TYPE_ID[bet_type]
            tx_info = bet.compose(db, source, feed_address,
                              bet_type_id, deadline, wager,
                              counterwager, target_value,
                              leverage, expiration)
            return bitcoin.transaction(tx_info, multisig)

        @dispatcher.add_method
        def create_broadcast(source, fee_fraction, text, timestamp, value=-1, multisig=config.MULTISIG):
            tx_info = broadcast.compose(db, source, timestamp,
                                    value, fee_fraction, text)
            return bitcoin.transaction(tx_info, multisig)

        @dispatcher.add_method
        def create_btcpay(order_match_id, multisig=config.MULTISIG):
            tx_info = btcpay.compose(db, order_match_id)
            return bitcoin.transaction(tx_info, multisig)

        @dispatcher.add_method
        def create_burn(source, quantity, multisig=config.MULTISIG):
            tx_info = burn.compose(db, source, quantity)
            return bitcoin.transaction(tx_info, multisig)

        @dispatcher.add_method
        def create_cancel(offer_hash, multisig=config.MULTISIG):
            tx_info = cancel.compose(db, offer_hash)
            return bitcoin.transaction(tx_info, multisig)

        @dispatcher.add_method
        def create_callback(source, fraction, asset, multisig=config.MULTISIG):
            tx_info = callback.compose(db, source, fraction, asset)
            return bitcoin.transaction(tx_info, multisig)

        @dispatcher.add_method
        def create_dividend(source, quantity_per_unit, asset, multisig=config.MULTISIG):
            tx_info = dividend.compose(db, source, quantity_per_unit,
                                   asset)
            return bitcoin.transaction(tx_info, multisig)

        @dispatcher.add_method
        def create_issuance(source, asset, quantity, divisible, description, callable_=None, call_date=None, call_price=None, transfer_destination=None, multisig=config.MULTISIG):
            try:
                quantity = int(quantity)
            except ValueError:
                raise Exception("Invalid quantity")
            tx_info = issuance.compose(db, source, transfer_destination,
                                   asset, quantity, divisible, callable_,
                                   call_date, call_price, description)
            return bitcoin.transaction(tx_info, multisig)

        @dispatcher.add_method
        def create_order(source, give_asset, give_quantity, get_asset, get_quantity, expiration, fee_required, fee_provided, multisig=config.MULTISIG):
            tx_info = order.compose(db, source, give_asset,
                                give_quantity, get_asset,
                                get_quantity, expiration,
                                fee_required, fee_provided)
            return bitcoin.transaction(tx_info, multisig)

        @dispatcher.add_method
        def create_send(source, destination, asset, quantity, multisig=config.MULTISIG):
            tx_info = send.compose(db, source, destination, asset, quantity)
            return bitcoin.transaction(tx_info, multisig)
                
        @dispatcher.add_method
        def transmit(unsigned_tx_hex):
            return bitcoin.transmit(unsigned_tx_hex)

        class API(object):
            @cherrypy.expose
            def index(self):
                cherrypy.response.headers["Content-Type"] = "application/json"
                cherrypy.response.headers["Access-Control-Allow-Origin"] = '*'
                cherrypy.response.headers["Access-Control-Allow-Methods"] = 'POST, GET, OPTIONS'
                cherrypy.response.headers["Access-Control-Allow-Headers"] = 'Origin, X-Requested-With, Content-Type, Accept'

                if cherrypy.request.method == "OPTIONS": #web client will send us this before making a request
                    return

                try:
                    data = cherrypy.request.body.read().decode('utf-8')
                except ValueError:
                    raise cherrypy.HTTPError(400, 'Invalid JSON document')
                response = JSONRPCResponseManager.handle(data, dispatcher)
                return response.json.encode()

        cherrypy.config.update({
            'log.screen': False,
            "environment": "embedded",
            'log.error_log.propagate': False,
            'log.access_log.propagate': False,
            "server.logToScreen" : False
        })
        checkpassword = cherrypy.lib.auth_basic.checkpassword_dict(
            {config.RPC_USER: config.RPC_PASSWORD})
        app_config = {
            '/': {
                'tools.trailing_slash.on': False,
                'tools.auth_basic.on': True,
                'tools.auth_basic.realm': 'counterpartyd',
                'tools.auth_basic.checkpassword': checkpassword,
            },
        }
        application = cherrypy.Application(API(), script_name="/jsonrpc/", config=app_config)

        #disable logging of the access and error logs to the screen
        application.log.access_log.propagate = False
        application.log.error_log.propagate = False

        if config.PREFIX != config.UNITTEST_PREFIX:  #skip setting up logs when for the test suite
            #set up a rotating log handler for this application
            # Remove the default FileHandlers if present.
            application.log.error_file = ""
            application.log.access_file = ""
            maxBytes = getattr(application.log, "rot_maxBytes", 10000000)
            backupCount = getattr(application.log, "rot_backupCount", 1000)
            # Make a new RotatingFileHandler for the error log.
            fname = getattr(application.log, "rot_error_file", os.path.join(config.DATA_DIR, "api.error.log"))
            h = logging_handlers.RotatingFileHandler(fname, 'a', maxBytes, backupCount)
            h.setLevel(logging.DEBUG)
            h.setFormatter(cherrypy._cplogging.logfmt)
            application.log.error_log.addHandler(h)
            # Make a new RotatingFileHandler for the access log.
            fname = getattr(application.log, "rot_access_file", os.path.join(config.DATA_DIR, "api.access.log"))
            h = logging_handlers.RotatingFileHandler(fname, 'a', maxBytes, backupCount)
            h.setLevel(logging.DEBUG)
            h.setFormatter(cherrypy._cplogging.logfmt)
            application.log.access_log.addHandler(h)

        #start up the API listener/handler
        server = wsgiserver.CherryPyWSGIServer(
            (config.RPC_HOST, int(config.RPC_PORT)), application)
        #logging.debug("Initializing API interface…")
        try:
            server.start()
        except OSError:
            raise Exception("Cannot start the API subsystem. Is counterpartyd"
                " already running, or is something else listening on port %s?" % config.RPC_PORT)

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
