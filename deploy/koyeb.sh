#!/bin/bash
koyeb secrets create API_ID --value="$API_ID"
koyeb secrets create API_HASH --value="$API_HASH"
koyeb secrets create BOT_TOKEN --value="$BOT_TOKEN"
koyeb secrets create ADMIN_IDS --value="$ADMIN_IDS"
koyeb app deploy teleguard --git-repository="$(git config --get remote.origin.url)" --git-branch=main
