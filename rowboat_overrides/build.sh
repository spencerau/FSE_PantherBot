

docker compose -f rowboat/docker-compose.yml -f rowboat_overrides/docker-compose.local.yml down
docker compose -f rowboat/docker-compose.yml -f rowboat_overrides/docker-compose.local.yml up -d