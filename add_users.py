#!/usr/bin/env python3

##############################################################################
#
#  Run this script to add users to the leaderboard. It can be run multiple
#  times before, during, or after an event.
#
#  Before running, be sure to change "db_name" to the database name used
#  in the create_event.py script for this event.
#
#  Editing users on the list will not overwrite old settings already stored
#  in the database. If you need to make a change (e.g. to correct a
#  discord_name) uncomment the lines at the bottom.
#
##############################################################################

import firebase_admin
from firebase_admin import credentials, firestore

event_name = 'event_db_name'
contestants = {
    'uyzr.wam' : u'digipedro',
    'someone.wam' : u'discord_name'
}

# Cloud Firestore setup

cred = credentials.Certificate('firebase-adminsdk-credentials.json')
firebase_admin.initialize_app(cred)
db = firestore.client()


# Add contestants to the "pending_contestants" database

doc_ref = db.collection(event_name).document('pending_contestants')
pending_contestants = doc_ref.get().to_dict()
if pending_contestants:
    pending_contestants.update(contestants)
else:
    pending_contestants = contestants
doc_ref.set(pending_contestants)


# Uncomment the code below by removing the ''' lines to overwrite previous
# settings for a user and force a reload of all their actions.
# If the api_read.py script is running, stop it before running the code below,
# then restart api_read.py

'''
wallet = 'uyzr.wam'
discord_name = u'digipedro'
contestants = db.collection(event_name).document('contestants').get().to_dict()
contestants[wallet] = {'stop_at_trx' : '', 'discord_name' : discord_name}
db.collection(event_name).document('contestants').set(contestants)
leaderboard = db.collection(event_name).document('leader_board').get().to_dict()
leaderboard[wallet] = {
        'discord_name' : discord_name,
        'total_tlm' : 0,
        'mine_count' : 0,
        'nft_count' : 0,
        'last_mine' : '',
        'nft_rarity' : {}
    }
db.collection(event_name).document('leader_board').set(leaderboard)
'''