#!/usr/bin/env python3

##############################################################################
#
#  Run this script continuously during an event to query the WAX api and
#  update the leaderboard. Run "crete_event.py" first to intitalize the
#  database.
#
#  Before running, be sure to change "db_name" to the database name used
#  in the create_event.py script for this event.
#
#  Press CTRL+C to stop the script. This can be done any time
#  loosing any information, when restarted it will re-query to be sure it has
#  all relevant mining data. Be sure it has completed at least 1 full cycle
#  after then end time of the event to ensure it has all data.
#
#
#  This script runs an infinite loop, checking the WAX blockchain for activity
#  by each contestant during the event, validating it took place on the right
#  land, then adding the data to the leaderboard.
#
##############################################################################

import requests
import json
import time
from datetime import datetime, timezone, timedelta
import firebase_admin
from firebase_admin import credentials, firestore

event_name = 'event_db_name'
contestants = {}
trx_to_load = []

# Cloud Firestore setup

cred = credentials.Certificate('firebase-adminsdk-credentials.json')
firebase_admin.initialize_app(cred)
db = firestore.client()


event = db.collection(event_name).document('details').get().to_dict()
event['start_time'] = datetime.fromisoformat(event['start_time'])
event['end_time'] = datetime.fromisoformat(event['end_time'])

# Get current time and format it for log messages

def curtime():
    return datetime.now().strftime('%H:%M:%S')

# Do a WAX api query and return the response or throw an exception

def apiCall(URL):
    resp = requests.get(URL)
    if resp.status_code != 200:
        print (curtime(), 'Problem pulling wallet data:', resp.reason)
        raise Exception()
    return resp

# Look through the transaction history for a contestant. It starts with newest actions 
# and grabs 10 at a time, recursively grabbing 10 more until it is sure it has overlapped
# with a transaction we've already seen or it reaches back to the start time of the event.
#
# Right now we're just grabbing relevant transaction IDs for mining event, we'll later query 
# full transaction data. For NFTs we can log all data now but still need to validate it
#
# addr = WAX wallet address
# grab_time = time to start looking at transaction history
#             (usually current time or event end time)
# skip = number of transaction to skip as we're looking back through time,
#        usually 10 at a time to avoid API throttling
# newest_trx = set blank to start, will be set to most recent transaction we've
#              processed so we don't have to read a user's full transaction history
#              every time

def getActions(addr, grab_time, skip, newest_trx):
    print(curtime(), 'Getting 10 actions for', addr)
    
    URL = f'https://wax.eosrio.io/v2/history/get_actions?account={addr}&limit=10&simple=true&before={grab_time}&skip={skip}'
    
    while True:
        try:
            resp = apiCall(URL)
            break
        except:
            print (curtime(), 'API query failed, retrying in 5 seconds.')
            time.sleep(5)
    
    actions = resp.json().get('simple_actions')
    if (not actions):
        print ('No data')
        return newest_trx
    
    stop_at_trx = contestants[addr]['stop_at_trx']

    for action in actions:
        trx_id = action.get('transaction_id')
        
        # First check if we've already processed this transaction, if so we can stop here.
        if trx_id == stop_at_trx:
            return newest_trx
        
        # If we haven't processed a new transaction and have looked at 20 irrelevant
        # transactions, we can set this as the transaction to stop at next time. The API returns
        # mining data as two actions with the same transaction_id but only one action has the relevant data
        # so we don't want to stop after reading just 10 or we might miss one when the irrelevant action
        # is the last of 10 and the relevant one with the same transaction_id comes right after
        if (newest_trx == '' and skip > 10):
            newest_trx = action.get('transaction_id')            
        
        timestamp = datetime.fromisoformat(action.get('timestamp'))
        if (timestamp < event['start_time']):
            print ('Reached back to event start time')
            return newest_trx
        if (action.get('data').get('from') == 'm.federation' and action.get('data').get('memo') == 'ALIEN WORLDS - Mined Trilium'):
            if newest_trx == '':
                newest_trx = action.get('transaction_id')
            trx_to_load.append(action.get('transaction_id'))
        elif (action.get('action') == 'logmint' and action.get('data').get('authorized_minter') == 'm.federation'):
            # NFT actions aren't stored with info about the land mined, we'll validate on which land this was obtained later
            nft_data = {
                'asset_id' : action.get('data').get('asset_id'),
                'timestamp' : action.get('timestamp'),
                'miner' : action.get('data').get('new_asset_owner'),
                'validated' : False
            }
            tdata = action.get('data').get('immutable_template_data')
            for entry in tdata:
                if entry.get('key') == 'name':
                    nft_data['name'] = entry.get('value')[1]
                if entry.get('key') == 'rarity':
                    nft_data['rarity'] = entry.get('value')[1]
            db.collection(event_name).document('data').collection('logmint').document(action.get('transaction_id')).set(nft_data)
            print(curtime(), 'Added NFT ', nft_data['asset_id'])

    return getActions(addr, grab_time, skip + 10, newest_trx)

# Read full transaction data for a mining event to get the stats and sure it was
# done on the land for our event. If so add it to the mine log in our database.
# Keeping a log of all transactions ensures this script
# can be started and stopped without risk of missing or double-counting events
def getTransactions(trx_id):
    print(curtime(), 'Reading', trx_id, end='')
    
    URL = f'https://wax.eosrio.io/v2/history/get_transaction?id={trx_id}'
    
    while True:
        try:
            resp = apiCall(URL)
            break
        except:
            time.sleep(5)
    
    actions = resp.json().get('actions')
    logmineDB = db.collection(event_name).document('data').collection('logmine')
    
    for action in actions:
        if (action.get('act').get('name') == 'logmine'):
            if (action.get('act').get('data').get('land_id') == event['land_id']):
                bounty = float(action.get('act').get('data').get('bounty')[:-4])
                try:
                    logmineDB.document(trx_id).set({
                        'miner': action.get('act').get('data').get('miner'),
                        'bounty': bounty,
                        'timestamp': action.get('@timestamp')
                    })
                except Exception as error:
                    print(' !!! NOT RECORDED !!!')
                    print(error);
                    
                print(' got', bounty)
                break
            else:
                print ('... wrong land!')
                break


# Look through the processed mining transactions in the database to update a user's stats
# This is also when we validate NFT finds, ensuring they were found on event land
# and not somewhere else
def updateUserStats(wallet):
    user_stats = {
        'total_tlm' : 0,
        'mine_count' : 0,
        'last_mine' : '',
        'nft_count' : 0,
        'nft_rarity' : {},
        'discord_name' : contestants[wallet]['discord_name']
    }
    
    # First total up TLM and get a count on mines
    mine_docs = db.collection(event_name).document('data').collection('logmine').where('miner', '==', wallet).stream()
    all_mines = []

    for mine in mine_docs:
        mine_data = mine.to_dict()
        all_mines.append(mine_data)
        user_stats['total_tlm'] += mine_data['bounty']
        user_stats['mine_count'] += 1
        timestamp = datetime.fromisoformat(mine_data['timestamp'])
        if (user_stats['last_mine'] == '' or timestamp >  user_stats['last_mine']):
            user_stats['last_mine'] = timestamp
    
    if (user_stats['last_mine'] != ''):
        user_stats['last_mine'] = user_stats['last_mine'].isoformat()
    
    # Now validate NFT finds and tally them up
    mint_docs = db.collection(event_name).document('data').collection('logmint').where('miner', '==', wallet).stream()
    for mint in mint_docs:
        mint_data = mint.to_dict()
        if (mint_data['validated'] == False):
            mint_timestamp = datetime.fromisoformat(mint_data['timestamp'])
            for mine_data in all_mines:
                mine_timestamp = datetime.fromisoformat(mine_data['timestamp'])
                # The id of the land isn't stored on the blockchain. If there was a minining event withing 30 seconds
                # of the NFT we can be sure it was that mine that did it. Most NTFs are logged in 6 seconds or less of
                # the mining event
                if (abs(int((mint_timestamp - mine_timestamp).total_seconds())) < 30):
                    print('Validated NFT with mine ' + str((mint_timestamp - mine_timestamp).total_seconds()) + ' secs apart');
                    mint_data['validated'] = True;
                    db.collection(event_name).document('data').collection('logmint').document(mint.id).set(mint_data)
                    break;
        if (mint_data['validated']):
            user_stats['nft_count'] += 1
            if (mint_data['rarity'] in user_stats['nft_rarity']):
                user_stats['nft_rarity'][mint_data['rarity']] += 1
            else:
                user_stats['nft_rarity'][mint_data['rarity']] = 1
    
    leader_board[wallet] = user_stats
    print(curtime(), 'Updated stats for', wallet)


# Here is the main progrom loop which will run until you CTRL+C out of it

while True:
    # grab_time is the most recent time we'll look for actions
    grab_time = datetime.utcnow()
    if (grab_time > event['end_time']):
        grab_time = event['end_time']
    if (grab_time < event['start_time']):
        print(curtime(), "Event hasn't started yet, pausing for 20 seconds.")
        time.sleep(20)
        continue

    # Load the latest contestant list and leader board
    contestants = db.collection(event_name).document('contestants').get().to_dict()
    leader_board = db.collection(event_name).document('leader_board').get().to_dict()

    # See if we have new contestants to add to the list
    pending_contestants = db.collection(event_name).document('pending_contestants').get().to_dict()
    if pending_contestants:
        for wallet in pending_contestants.keys():
            print (wallet)
            if wallet not in contestants:
                contestants[wallet] = {'stop_at_trx' : '', 'discord_name' : pending_contestants[wallet]}
                leader_board[wallet] =  {
                    'discord_name' : pending_contestants[wallet],
                    'total_tlm' : 0,
                    'mine_count' : 0,
                    'nft_count' : 0,
                    'last_mine' : '',
                    'nft_rarity' : {}
                }
        db.collection(event_name).document('contestants').set(contestants)
        db.collection(event_name).document('leader_board').set(leader_board)
        db.collection(event_name).document('pending_contestants').set({})
    
    # For each user in the contestant list, load their data from the WAX blockchain
    for wallet in contestants.keys():        
        stop_at_trx = getActions(wallet, grab_time.isoformat(), 0, '')
        print(curtime(), len(trx_to_load), 'new transactiong to load.')
        
        if (stop_at_trx != ''):
            contestants[wallet]['stop_at_trx'] = stop_at_trx
            db.collection(event_name).document('contestants').set(contestants)
    
        if (len(trx_to_load) > 0):
            for trx_id in trx_to_load:
                getTransactions(trx_id)
    
            trx_to_load = []
            print(curtime(), 'All transactions processed.')
            updateUserStats(wallet)
    
    # Now that we've processed each user once, update the database,
    # take a breath, and do it all over again.
    db.collection(event_name).document('leader_board').set(leader_board)
    
    print(curtime(), '=============== Pausing for next cycle ===============')
    time.sleep(10)

