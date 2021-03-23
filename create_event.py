#!/usr/bin/env python3

##############################################################################
#
#  Run this script once to create and initialize a new Firestore database
#  for an event
#
#  Before running, be sure to change "event_name" to a unique name for
#  the event database
#  start_time and end_time shoud be in UTC timezone.
#
##############################################################################

from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore

event_name = 'event_db_name'

# Cloud Firestore setup

cred = credentials.Certificate('firebase-adminsdk-credentials.json')
firebase_admin.initialize_app(cred)
db = firestore.client()

# Put the event information below

doc_ref = db.collection(event_name).document('details')
doc_ref.set({
    'start_time' : datetime(2021, 3, 20, 19, 0, 0, 0).isoformat(),
    'end_time' : datetime(2021, 3, 21, 19, 0, 0, 0).isoformat(),
    'name' : 'Truffle Hunter Mining Contest',
    'location_info' : 'Neri 28:16 Mushroom Forest',
    'time_info' : 'Starting March 20, 2021 - 1900 / 7pm UTC for 24 hours',
    'land_id' : '1099512960104',
    'land_img' : 'https://cloudflare-ipfs.com/ipfs/QmUSFaBbZDj5pYp9BKRagpDJYNkBbjpsDeJaW3oCoDmK2f',
})

# Start with at least one contestant, or you can add more

contestants = {
    'uyzr.wam' : {'stop_at_trx' : '', 'discord_name' : u'digipedro'},
}

# No need to change anything below here

doc_ref = db.collection(event_name).document('contestants')
doc_ref.set(contestants)

doc_ref = db.collection(event_name).document('pending_contestants')
doc_ref.set({})

leader_board = {}
for wallet in contestants.keys():
    leader_board[wallet] =  {
        'discord_name' : contestants[wallet]['discord_name'],
        'total_tlm' : 0,
        'mine_count' : 0,
        'nft_count' : 0,
        'last_mine' : '',
        'nft_rarity' : {}
    }
doc_ref = db.collection(event_name).document('leader_board')
doc_ref.set(leader_board)
