docker compose -f docker-compose.prod.yml restart django

docker compose -f docker-compose.prod.yml -f docker-compose.prod.livekit.yml restart