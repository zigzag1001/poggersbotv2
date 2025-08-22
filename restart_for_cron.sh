# 0 3 * * *
cd /home/opc/bot/poggersbotv2 &&
    sudo docker compose build --build-arg CACHEBUST=$(date +%s) &&
    sudo docker compose up -d &&
    sudo docker image prune -af
# REPLACE DIR WITH YOUR OWN IF USING THIS
