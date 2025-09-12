#!/bin/bash
heroku create teleguard-bot
heroku config:set API_ID=$API_ID API_HASH=$API_HASH BOT_TOKEN=$BOT_TOKEN ADMIN_IDS=$ADMIN_IDS
heroku addons:create heroku-postgresql:mini
git push heroku main
