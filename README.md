# aw_leaderboard

This is a simple leaderboard webpage for cryptomonKey mining events on Alien Worlds.

## Live Webpage

https://digipedro.github.io/aw_leaderboard/

## What's All This Then?

Learn more about cryptomonKeys : https://cryptomonkeys.cc/

Learn more abour Alien Worlds : https://alienworlds.io/

## To Run An Event

- Setup a Google Firestore account and generate a credentials file.

- Edit the "create_event.py" with event info and run it.

- Edit the "add_users.py" script with contestant names and run it. You can re-run this many times to add contestants before, during, or after the event.

- When the event starts, run the "api_read.py" script and keep it running until the end of the event.